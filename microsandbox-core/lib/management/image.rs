//! Container image management for Microsandbox.
//!
//! This module provides functionality for managing container images from various
//! registries. It supports pulling images from Docker and Sandboxes.io registries,
//! handling image layers, and managing the local image cache.

use crate::{
    management::db::{self, OCI_DB_MIGRATOR},
    oci::{DockerRegistry, OciRegistryPull, Reference},
    MicrosandboxError, MicrosandboxResult,
};
#[cfg(feature = "cli")]
use flate2::read::GzDecoder;
use futures::future;
use serde_json;
#[cfg(feature = "cli")]
use indicatif::{ProgressBar, ProgressStyle};
#[cfg(feature = "cli")]
use microsandbox_utils::term::{self, MULTI_PROGRESS};
use microsandbox_utils::{env, EXTRACTED_LAYER_SUFFIX, LAYERS_SUBDIR, OCI_DB_FILENAME};
use sqlx::{Pool, Sqlite};
#[cfg(feature = "cli")]
use std::io::Result as IoResult;
use std::path::{Path, PathBuf};
use std::ffi::CStr;
use std::io::Read;
use tar::Archive;
use tempfile::tempdir;
use tokio::fs;
#[cfg(feature = "cli")]
use tokio::task::spawn_blocking;

//--------------------------------------------------------------------------------------------------
// Constants
//--------------------------------------------------------------------------------------------------

/// The domain name for the Docker registry.
const DOCKER_REGISTRY: &str = "docker.io";

/// The domain name for the Sandboxes registry.
const SANDBOXES_REGISTRY: &str = "sandboxes.io";

#[cfg(feature = "cli")]
/// Spinner message used for extracting layers.
const EXTRACT_LAYERS_MSG: &str = "Extracting layers";

//--------------------------------------------------------------------------------------------------
// Functions
//--------------------------------------------------------------------------------------------------

/// Pulls an image or image group from a supported registry (Docker or Sandboxes.io).
///
/// This function handles pulling container images from different registries based on the provided
/// parameters. It supports both single image pulls and image group pulls (for Sandboxes.io registry only).
///
/// For Sandboxes.io registry:
/// - Library repository images are pulled from Docker registry for compatibility
/// - Other namespaces are also pulled from Docker registry with a warning about potential future changes
///
/// ## Arguments
///
/// * `name` - The reference to the image or image group to pull
/// * `image` - If true, indicates that a single image should be pulled
/// * `image_group` - If true, indicates that an image group should be pulled (Sandboxes.io only)
/// * `layer_path` - The path to store the layer files
///
/// ## Errors
///
/// Returns an error in the following cases:
/// * Both `image` and `image_group` are true (invalid combination)
/// * Image group pull is requested for a non-Sandboxes.io registry
/// * Unsupported registry is specified
/// * Registry-specific pull operations fail
///
/// # Examples
///
/// ```no_run
/// use microsandbox_core::management::image;
/// use microsandbox_core::oci::Reference;
/// use std::path::PathBuf;
///
/// # #[tokio::main]
/// # async fn main() -> anyhow::Result<()> {
/// // Pull a single image from Docker registry
/// image::pull("docker.io/library/ubuntu:latest".parse().unwrap(), true, false, None).await?;
///
/// // Pull an image from Sandboxes.io registry
/// image::pull("sandboxes.io/library/alpine:latest".parse().unwrap(), true, false, None).await?;
///
/// // Pull an image from the default registry (when no registry is specified in the reference)
/// image::pull("nginx:latest".parse().unwrap(), true, false, None).await?;
///
/// // You can set the OCI_REGISTRY_DOMAIN environment variable to specify your default registry
/// std::env::set_var("OCI_REGISTRY_DOMAIN", "docker.io");
/// image::pull("alpine:latest".parse().unwrap(), true, false, None).await?;
///
/// // Pull an image from Docker registry and store the layers in a custom directory
/// image::pull("docker.io/library/ubuntu:latest".parse().unwrap(), true, Some(PathBuf::from("/custom/path"))).await?;
/// # Ok(())
/// # }
/// ```
pub async fn pull(
    name: Reference,
    _image: bool,
    layer_path: Option<PathBuf>,
) -> MicrosandboxResult<()> {
    // Single image pull mode (default if both flags are false, or if image is true)
    let registry = name.to_string().split('/').next().unwrap_or("").to_string();
    let temp_download_dir = tempdir()?.into_path();

    tracing::info!(
        "temporary download directory: {}",
        temp_download_dir.display()
    );
    
    println!("KIRO DEBUG: Starting pull for image: {}, registry: {}", name, registry);
    tracing::info!("KIRO DEBUG: Starting pull for image: {}, registry: {}", name, registry);

    // Only try local Docker daemon for images that might be local builds
    // Check if this looks like a local image (contains "local" in the name or is not from official registry)
    let image_name = name.to_string();
    let should_try_local_first = image_name.contains("local") || 
                                 image_name.contains("localhost") ||
                                 !image_name.starts_with("docker.io/microsandbox/");
    
    if should_try_local_first {
        tracing::info!("attempting to pull image {} from local Docker daemon first (detected as local image)", name);
        match pull_from_local_docker(&name, &temp_download_dir, layer_path.clone()).await {
            Ok(()) => {
                tracing::info!("successfully pulled image {} from local Docker daemon", name);
                return Ok(());
            }
            Err(e) => {
                tracing::warn!("failed to pull from local Docker daemon: {}, trying remote registries", e);
            }
        }
    }

    // If local pull fails, try remote registries based on registry type
    if registry == DOCKER_REGISTRY {
        pull_from_docker_registry(&name, &temp_download_dir, layer_path).await
    } else if registry == SANDBOXES_REGISTRY {
        pull_from_sandboxes_registry(&name, &temp_download_dir, layer_path).await
    } else {
        Err(MicrosandboxError::InvalidArgument(format!(
            "Unsupported registry: {}",
            registry
        )))
    }
}

/// Pulls a single image from the local Docker daemon.
///
/// This function attempts to export an image from the local Docker daemon
/// using `docker save` command and then processes it like a registry pull.
///
/// ## Arguments
///
/// * `image` - The reference to the Docker image to pull from local daemon
/// * `download_dir` - The directory to download the image layers to
/// * `layer_path` - Optional custom path to store layers
///
/// ## Errors
///
/// Returns an error if:
/// * Docker daemon is not running
/// * Image doesn't exist locally
/// * Failed to export or process the image
pub async fn pull_from_local_docker(
    image: &Reference,
    download_dir: impl AsRef<Path>,
    layer_path: Option<PathBuf>,
) -> MicrosandboxResult<()> {
    println!("KIRO DEBUG: pull_from_local_docker called for image: {}", image);
    use std::process::Stdio;
    use tokio::process::Command;
    
    let download_dir = download_dir.as_ref();
    let microsandbox_home_path = env::get_microsandbox_home_path();
    let db_path = microsandbox_home_path.join(OCI_DB_FILENAME);

    // Use custom layer_path if specified, otherwise use default microsandbox layers directory
    let layers_dir = match layer_path {
        Some(path) => path,
        None => microsandbox_home_path.join(LAYERS_SUBDIR),
    };

    // Create layers directory if it doesn't exist
    fs::create_dir_all(&layers_dir).await?;

    // Get or create a connection pool to the database
    let pool = db::get_or_create_pool(&db_path, &OCI_DB_MIGRATOR).await?;

    // For local Docker pulls, we always try to pull from Docker daemon
    // even if the image exists in our database, in case it has been updated locally
    tracing::info!("attempting to pull image {} from local Docker daemon", image);

    // Try to export the image from local Docker daemon
    let image_name = image.to_string();
    let tar_path = download_dir.join("image.tar");
    
    let output = Command::new("docker")
        .args(&["save", "-o", tar_path.to_str().unwrap(), &image_name])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .await
        .map_err(|e| MicrosandboxError::InvalidArgument(format!(
            "Failed to execute docker save command: {}",
            e
        )))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(MicrosandboxError::InvalidArgument(format!(
            "Docker save failed: {}",
            stderr
        )));
    }

    tracing::info!("successfully exported image {} from local Docker daemon", image);

    // Now we need to extract the tar file and process it like a registry pull
    // This is a simplified implementation - in a full implementation, you'd want to
    // properly parse the Docker image format and extract layers

    // Extract the tar file to simulate registry download
    let tar_file = std::fs::File::open(&tar_path)
        .map_err(|e| MicrosandboxError::InvalidArgument(format!(
            "Failed to open exported tar file: {}",
            e
        )))?;
    
    let mut archive = tar::Archive::new(tar_file);
    archive.unpack(download_dir)
        .map_err(|e| MicrosandboxError::InvalidArgument(format!(
            "Failed to extract exported tar file: {}",
            e
        )))?;

    // Docker save format is different from registry format
    // Let's first see what we have in the download directory
    tracing::info!("Examining Docker save output in: {}", download_dir.display());
    let mut read_dir = fs::read_dir(download_dir).await?;
    while let Ok(Some(entry)) = read_dir.next_entry().await {
        let path = entry.path();
        tracing::info!("Found: {} (is_dir: {})", path.display(), path.is_dir());
        if path.is_dir() {
            let mut sub_read_dir = fs::read_dir(&path).await?;
            while let Ok(Some(sub_entry)) = sub_read_dir.next_entry().await {
                let sub_path = sub_entry.path();
                tracing::info!("  Sub-item: {}", sub_path.display());
            }
        }
    }
    
    // Handle OCI format from Docker save
    let mut layer_paths = Vec::new();
    let mut docker_config_digest: Option<String> = None;
    let mut docker_layers: Vec<String> = Vec::new();
    let blobs_dir = download_dir.join("blobs").join("sha256");
    
    if blobs_dir.exists() {
        tracing::info!("Found OCI blobs directory: {}", blobs_dir.display());
        
        // Read the manifest to identify which blobs are layers
        let manifest_path = download_dir.join("manifest.json");
        
        if manifest_path.exists() {
            let manifest_content = fs::read_to_string(&manifest_path).await?;
            tracing::info!("Manifest content: {}", manifest_content);
            
            // Parse the Docker manifest.json to extract config and layer info
            if let Ok(manifest_array) = serde_json::from_str::<Vec<serde_json::Value>>(&manifest_content) {
                if let Some(manifest_obj) = manifest_array.first() {
                    if let Some(config_path) = manifest_obj.get("Config").and_then(|v| v.as_str()) {
                        docker_config_digest = Some(config_path.to_string());
                    }
                    if let Some(layers_array) = manifest_obj.get("Layers").and_then(|v| v.as_array()) {
                        docker_layers = layers_array.iter()
                            .filter_map(|v| v.as_str().map(|s| s.to_string()))
                            .collect();
                    }
                }
            }
            
            // Parse the manifest to find layer digests
            // For now, let's use a simple heuristic: check if the blob is gzip compressed
            let mut read_dir = fs::read_dir(&blobs_dir).await?;
            
            while let Ok(Some(entry)) = read_dir.next_entry().await {
                let path = entry.path();
                if path.is_file() {
                    // Check if this blob is a gzip-compressed layer
                    let mut file = std::fs::File::open(&path)?;
                    let mut header = [0u8; 2];
                    use std::io::Read;
                    if file.read_exact(&mut header).is_ok() && header == [0x1f, 0x8b] {
                        // This is a gzip file, likely a layer
                        let file_name = path.file_name().unwrap().to_string_lossy();
                        let sha256_name = format!("sha256:{}", file_name);
                        let new_path = download_dir.join(&sha256_name);
                        
                        // Copy the blob to the new location with sha256: prefix
                        fs::copy(&path, &new_path).await?;
                        
                        tracing::info!("Found layer blob: {} -> {}", path.display(), new_path.display());
                        layer_paths.push(new_path);
                    } else {
                        tracing::info!("Skipping non-layer blob: {}", path.display());
                    }
                }
            }
        } else {
            tracing::warn!("No manifest.json found, processing all blobs");
            // Fallback: process all blobs but handle errors gracefully
            let mut read_dir = fs::read_dir(&blobs_dir).await?;
            
            while let Ok(Some(entry)) = read_dir.next_entry().await {
                let path = entry.path();
                if path.is_file() {
                    let file_name = path.file_name().unwrap().to_string_lossy();
                    let sha256_name = format!("sha256:{}", file_name);
                    let new_path = download_dir.join(&sha256_name);
                    
                    // Copy the blob to the new location with sha256: prefix
                    fs::copy(&path, &new_path).await?;
                    
                    tracing::info!("Found blob: {} -> {}", path.display(), new_path.display());
                    layer_paths.push(new_path);
                }
            }
        }
    } else {
        // Fallback: look for traditional layer.tar files
        let mut read_dir = fs::read_dir(download_dir).await?;
        
        while let Ok(Some(entry)) = read_dir.next_entry().await {
            let path = entry.path();
            if path.is_dir() {
                // Look for layer.tar files in subdirectories
                let layer_tar_path = path.join("layer.tar");
                if layer_tar_path.exists() {
                    // Create a sha256 filename for this layer
                    let dir_name = path.file_name().unwrap().to_string_lossy();
                    let sha256_name = if dir_name.len() >= 12 {
                        format!("sha256:{}", &dir_name[..64.min(dir_name.len())])
                    } else {
                        format!("sha256:{}", dir_name)
                    };
                    let new_path = download_dir.join(&sha256_name);
                    
                    // Copy the layer.tar to the new location
                    fs::copy(&layer_tar_path, &new_path).await?;
                    
                    tracing::info!("Found layer: {} -> {}", layer_tar_path.display(), new_path.display());
                    layer_paths.push(new_path);
                }
            }
        }
    }

    if layer_paths.is_empty() {
        return Err(MicrosandboxError::InvalidArgument(
            "No layers found in exported Docker image".to_string()
        ));
    }

    #[cfg(feature = "cli")]
    let extract_layers_sp = term::create_spinner(
        EXTRACT_LAYERS_MSG.to_string(),
        None,
        Some(layer_paths.len() as u64),
    );

    let extraction_futures: Vec<_> = layer_paths
        .into_iter()
        .map(|path| {
            let layers_dir = layers_dir.clone();
            #[cfg(feature = "cli")]
            let extract_layers_sp = extract_layers_sp.clone();
            async move {
                let result = extract_layer(path, &layers_dir).await;
                #[cfg(feature = "cli")]
                extract_layers_sp.inc(1);
                result
            }
        })
        .collect();

    // Wait for all extractions to complete
    for result in future::join_all(extraction_futures).await {
        result?;
    }

    #[cfg(feature = "cli")]
    extract_layers_sp.finish();

    // Register the image in the database
    let reference = image.to_string();
    let total_size = 0i64; // We don't have accurate size info from docker save
    
    tracing::info!("registering local Docker image {} in database", reference);
    let image_id = db::save_or_update_image(&pool, &reference, total_size).await?;
    
    // Try to create manifest and config from Docker save output
    if let Some(config_digest) = docker_config_digest {
        tracing::info!("attempting to create manifest and config for local image using Docker save data");
        
        // Read the config blob
        let config_blob_path = download_dir.join(&config_digest);
        if config_blob_path.exists() {
            match fs::read_to_string(&config_blob_path).await {
                Ok(config_content) => {
                    match serde_json::from_str::<oci_spec::image::ImageConfiguration>(&config_content) {
                        Ok(config) => {
                            // Create a minimal manifest
                            use oci_spec::image::{ImageManifest, Descriptor, MediaType, Digest};
                            
                            // Create layer descriptors from the Docker layers
                            let mut layer_descriptors = Vec::new();
                            for layer_path in &docker_layers {
                                if let Some(digest_part) = layer_path.strip_prefix("blobs/sha256/") {
                                    let digest_str = format!("sha256:{}", digest_part);
                                    if let Ok(digest) = digest_str.parse::<Digest>() {
                                        layer_descriptors.push(Descriptor::new(
                                            MediaType::ImageLayerGzip,
                                            0, // We don't have size info
                                            digest
                                        ));
                                    }
                                }
                            }
                            
                            // Create config descriptor
                            if let Some(config_digest_part) = config_digest.strip_prefix("blobs/sha256/") {
                                let config_digest_str = format!("sha256:{}", config_digest_part);
                                if let Ok(config_digest_parsed) = config_digest_str.parse::<Digest>() {
                                    let config_descriptor = Descriptor::new(
                                        MediaType::ImageConfig,
                                        0,
                                        config_digest_parsed
                                    );
                                    
                                    // Create manifest using serde_json to build the structure
                                    let manifest_json = serde_json::json!({
                                        "schemaVersion": 2,
                                        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                                        "config": config_descriptor,
                                        "layers": layer_descriptors
                                    });
                                    
                                    if let Ok(manifest) = serde_json::from_value::<ImageManifest>(manifest_json) {
                                        // Save manifest and config to database
                                        match db::save_manifest(&pool, image_id, None, &manifest).await {
                                            Ok(manifest_id) => {
                                                match db::save_config(&pool, manifest_id, &config).await {
                                                    Ok(_) => {
                                                        // Now save the layers and link them to the manifest
                                                        for layer_path in &docker_layers {
                                                            if let Some(digest_part) = layer_path.strip_prefix("blobs/sha256/") {
                                                                let digest_str = format!("sha256:{}", digest_part);
                                                                
                                                                // Save layer to database
                                                                match db::save_layer(&pool, "application/vnd.docker.image.rootfs.diff.tar.gzip", &digest_str, 0, &digest_str).await {
                                                                    Ok(layer_id) => {
                                                                        // Link layer to manifest
                                                                        if let Err(e) = db::save_manifest_layer(&pool, manifest_id, layer_id).await {
                                                                            tracing::warn!("failed to link layer {} to manifest for local image {}: {}", digest_str, reference, e);
                                                                        }
                                                                    }
                                                                    Err(e) => {
                                                                        tracing::warn!("failed to save layer {} for local image {}: {}", digest_str, reference, e);
                                                                    }
                                                                }
                                                            }
                                                        }
                                                        tracing::info!("successfully created manifest, config, and layers for local Docker image {}", reference);
                                                    }
                                                    Err(e) => {
                                                        tracing::warn!("failed to save config for local image {}: {}", reference, e);
                                                    }
                                                }
                                            }
                                            Err(e) => {
                                                tracing::warn!("failed to save manifest for local image {}: {}", reference, e);
                                            }
                                        }
                                    } else {
                                        tracing::warn!("failed to create manifest structure for local image {}", reference);
                                    }
                                } else {
                                    tracing::warn!("failed to parse config digest for local image {}", reference);
                                }
                            } else {
                                tracing::warn!("invalid config digest format for local image {}", reference);
                            }
                        }
                        Err(e) => {
                            tracing::warn!("failed to parse config JSON for local image {}: {}", reference, e);
                        }
                    }
                }
                Err(e) => {
                    tracing::warn!("failed to read config blob for local image {}: {}", reference, e);
                }
            }
        } else {
            tracing::warn!("config blob not found for local image {}", reference);
        }
    } else {
        tracing::warn!("no config digest found in Docker manifest for local image {}", reference);
    }

    tracing::info!("successfully processed and registered local Docker image {}", image);
    Ok(())
}

/// Pulls a single image from the Docker registry.
///
/// ## Arguments
///
/// * `image` - The reference to the Docker image to pull
/// * `download_dir` - The directory to download the image layers to
/// * `layer_path` - Optional custom path to store layers
///
/// ## Errors
///
/// Returns an error if:
/// * Failed to create temporary directories
/// * Failed to initialize Docker registry client
/// * Failed to pull the image from Docker registry
pub async fn pull_from_docker_registry(
    image: &Reference,
    download_dir: impl AsRef<Path>,
    layer_path: Option<PathBuf>,
) -> MicrosandboxResult<()> {
    let download_dir = download_dir.as_ref();
    let microsandbox_home_path = env::get_microsandbox_home_path();
    let db_path = microsandbox_home_path.join(OCI_DB_FILENAME);

    // Use custom layer_path if specified, otherwise use default microsandbox layers directory
    let layers_dir = match layer_path {
        Some(path) => path,
        None => microsandbox_home_path.join(LAYERS_SUBDIR),
    };

    // Create layers directory if it doesn't exist
    fs::create_dir_all(&layers_dir).await?;

    let docker_registry = DockerRegistry::new(download_dir, &db_path).await?;

    // Get or create a connection pool to the database
    let pool = db::get_or_create_pool(&db_path, &OCI_DB_MIGRATOR).await?;

    // Check if we need to pull the image
    if check_image_layers(&pool, image, &layers_dir).await? {
        tracing::info!("image {} and all its layers exist, skipping pull", image);
        return Ok(());
    }

    docker_registry
        .pull_image(image.get_repository(), image.get_selector().clone())
        .await?;

    // Find and extract layers in parallel
    let layer_paths = collect_layer_files(download_dir).await?;

    #[cfg(feature = "cli")]
    let extract_layers_sp = term::create_spinner(
        EXTRACT_LAYERS_MSG.to_string(),
        None,
        Some(layer_paths.len() as u64),
    );

    let extraction_futures: Vec<_> = layer_paths
        .into_iter()
        .map(|path| {
            let layers_dir = layers_dir.clone();
            #[cfg(feature = "cli")]
            let extract_layers_sp = extract_layers_sp.clone();
            async move {
                let result = extract_layer(path, &layers_dir).await;
                #[cfg(feature = "cli")]
                extract_layers_sp.inc(1);
                result
            }
        })
        .collect();

    // Wait for all extractions to complete
    for result in future::join_all(extraction_futures).await {
        result?;
    }

    #[cfg(feature = "cli")]
    extract_layers_sp.finish();

    Ok(())
}

/// Pulls a single image from the Sandboxes.io registry.
///
/// For library repository images, this function delegates to `pull_from_docker_registry` for compatibility.
/// For other namespaces, it also uses Docker registry but displays a warning about potential future changes.
///
/// ## Arguments
///
/// * `image` - The reference to the Sandboxes.io image to pull
/// * `download_dir` - The directory to download the image layers to
/// * `layer_path` - Optional custom path to store layers
///
/// ## Errors
///
/// Returns an error if the underlying Docker registry pull fails
pub async fn pull_from_sandboxes_registry(
    image: &Reference,
    download_dir: impl AsRef<Path>,
    layer_path: Option<PathBuf>,
) -> MicrosandboxResult<()> {
    // Check if this is a library repository image
    let repository = image.get_repository();

    // Create a Docker reference string using the original repository but with docker.io registry
    // Format: docker.io/repository:tag
    let docker_ref_str = format!(
        "{}/{}",
        DOCKER_REGISTRY,
        image
            .to_string()
            .split('/')
            .skip(1)
            .collect::<Vec<&str>>()
            .join("/")
    );
    let docker_reference: Reference = docker_ref_str.parse()?;

    if repository.starts_with("library/") {
        tracing::info!("pulling library image from Docker registry for compatibility");
    } else {
        tracing::warn!(
            "Non-library namespace image requested from Sandboxes registry: {}",
            repository
        );
        tracing::warn!(
            "Currently using Docker registry for compatibility, but namespace mappings may change in the future"
        );
        tracing::info!(
            "To ensure consistent behavior, consider setting OCI_REGISTRY_DOMAIN=docker.io if you want to use Docker registry consistently"
        );
    }

    pull_from_docker_registry(&docker_reference, download_dir, layer_path).await
}

/// Pulls an image group from the Sandboxes.io registry.
///
/// ## Arguments
///
/// * `group` - The reference to the image group to pull
/// ## Errors
///
/// Returns an error if:
/// * Sandboxes registry image group pull is not implemented
pub async fn pull_group_from_sandboxes_registry(_group: &Reference) -> MicrosandboxResult<()> {
    return Err(MicrosandboxError::NotImplemented(
        "Sandboxes registry image group pull is not implemented".to_string(),
    ));
}

//--------------------------------------------------------------------------------------------------
// Functions: Helpers
//--------------------------------------------------------------------------------------------------

/// Checks if all layers for an image exist in both the database and the layers directory.
///
/// ## Arguments
///
/// * `pool` - The database connection pool
/// * `image` - The reference to the image to check
/// * `layers_dir` - The directory where layers should be stored
///
/// ## Returns
///
/// Returns Ok(true) if all layers exist and are valid, Ok(false) if any layers are missing
/// or invalid. Any errors during the check process will return Ok(false) with a warning log.
async fn check_image_layers(
    pool: &Pool<Sqlite>,
    image: &Reference,
    layers_dir: impl AsRef<Path>,
) -> MicrosandboxResult<bool> {
    let layers_dir = layers_dir.as_ref();

    // Check if the image exists in the database
    match db::image_exists(pool, &image.to_string()).await {
        Ok(true) => {
            // Image exists, get all layer digests for this image
            match db::get_image_layer_digests(pool, &image.to_string()).await {
                Ok(layer_digests) => {
                    tracing::info!("layer_digests: {:?}", layer_digests);
                    if layer_digests.is_empty() {
                        tracing::warn!("no layers found for image {}", image);
                        return Ok(false);
                    }

                    // Check if all layers exist in the layers directory
                    for digest in &layer_digests {
                        let layer_path =
                            layers_dir.join(format!("{}.{}", digest, EXTRACTED_LAYER_SUFFIX));
                        if !layer_path.exists() {
                            tracing::warn!("layer {} not found in layers directory", digest);
                            return Ok(false);
                        }

                        // Also check that the layer directory actually has content
                        let mut read_dir = fs::read_dir(&layer_path).await?;
                        let dir_empty = read_dir.next_entry().await?.is_none();
                        if dir_empty {
                            tracing::warn!("layer {} exists but is empty", digest);
                        }

                        tracing::info!("layer {} found in layers directory", digest);
                    }

                    // Get the layers from database to verify database records exist for all digests
                    let db_layers = db::get_layers_by_digest(pool, &layer_digests).await?;

                    if db_layers.len() < layer_digests.len() {
                        tracing::warn!(
                            "some layers for image {} exist on disk but missing in db",
                            image
                        );
                        return Ok(false);
                    }

                    tracing::info!("all layers for image {} exist and are valid", image);
                    Ok(true)
                }
                Err(e) => {
                    tracing::warn!("error checking layer digests: {}, will pull image", e);
                    Ok(false)
                }
            }
        }
        Ok(false) => {
            tracing::warn!("image {} does not exist in db, will pull image", image);
            Ok(false)
        }
        Err(e) => {
            tracing::warn!("error checking image existence: {}, will pull image", e);
            Ok(false)
        }
    }
}

/// Helper function to get full mode with file type bits
fn get_full_mode(entry_type: &tar::EntryType, permission_bits: u32) -> u32 {
    let file_type_bits = if entry_type.is_file() {
        libc::S_IFREG as u32
    } else if entry_type.is_dir() {
        libc::S_IFDIR as u32
    } else if entry_type.is_symlink() {
        libc::S_IFLNK as u32
    } else if entry_type.is_block_special() {
        libc::S_IFBLK as u32
    } else if entry_type.is_character_special() {
        libc::S_IFCHR as u32
    } else if entry_type.is_fifo() {
        libc::S_IFIFO as u32
    } else {
        0 // Unknown type
    };

    file_type_bits | permission_bits
}

/// Helper function to set xattr with stat information
fn set_stat_xattr(
    path: &Path,
    xattr_name: &CStr,
    uid: u64,
    gid: u64,
    mode: u32,
) -> Result<(), MicrosandboxError> {
    use std::ffi::CString;

    let stat_data = format!("{}:{}:0{:o}", uid, gid, mode);
    let path_cstring = CString::new(path.as_os_str().as_encoded_bytes())
        .map_err(|e| MicrosandboxError::LayerExtraction(format!("Invalid path: {:?}", e)))?;

    let result = unsafe {
        #[cfg(target_os = "macos")]
        {
            libc::setxattr(
                path_cstring.as_ptr(),
                xattr_name.as_ptr(),
                stat_data.as_ptr() as *const libc::c_void,
                stat_data.len(),
                0, // position parameter for macOS
                0, // options
            )
        }
        #[cfg(target_os = "linux")]
        {
            libc::setxattr(
                path_cstring.as_ptr(),
                xattr_name.as_ptr(),
                stat_data.as_ptr() as *const libc::c_void,
                stat_data.len(),
                0, // flags
            )
        }
    };

    if result != 0 {
        let errno = std::io::Error::last_os_error();
        if errno.raw_os_error() == Some(libc::ENOTSUP) {
            tracing::warn!(
                "Filesystem does not support xattrs for {}, continuing without stat shadowing",
                path.display()
            );
        } else {
            return Err(MicrosandboxError::LayerExtraction(format!(
                "Failed to set xattr on {}: {}",
                path.display(),
                errno
            )));
        }
    }
    Ok(())
}

/// Extracts a layer from the downloaded tar.gz file into an extracted directory.
/// The extracted directory will be named as <layer-name>.extracted
/// Custom extraction function that modifies file ownership during extraction
fn extract_tar_with_ownership_override<R: Read>(
    archive: &mut Archive<R>,
    extract_dir: &Path,
) -> MicrosandboxResult<()> {
    use std::ffi::CString;
    use std::os::unix::fs::PermissionsExt;

    // Cache the xattr name to avoid repeated allocations
    let xattr_name = CString::new("user.containers.override_stat")
        .map_err(|e| MicrosandboxError::LayerExtraction(format!("Invalid attr name: {:?}", e)))?;

    // Structure to store hard link information
    struct HardLinkInfo {
        link_path: PathBuf,
        target_path: PathBuf,
        uid: u64,
        gid: u64,
        mode: u32,
    }

    // Store hard links to process after all regular files are extracted
    let mut hard_links = Vec::new();

    for entry in archive.entries()? {
        let mut entry =
            entry.map_err(|e| MicrosandboxError::LayerExtraction(format!("{:?}", e)))?;
        let path = entry
            .path()
            .map_err(|e| MicrosandboxError::LayerExtraction(format!("{:?}", e)))?;
        let full_path = extract_dir.join(&path);

        // Get the original metadata from the tar entry
        let original_uid = entry.header().uid()?;
        let original_gid = entry.header().gid()?;
        let permission_bits = entry.header().mode()?;

        // Check the entry type
        let entry_type = entry.header().entry_type();
        let is_symlink = entry_type.is_symlink();
        let is_hard_link = entry_type.is_hard_link();

        // Calculate the full mode with file type bits
        let original_mode = get_full_mode(&entry_type, permission_bits);

        // Handle hard links separately - collect them for processing after all files are extracted
        if is_hard_link {
            if let Ok(Some(link_name)) = entry.link_name() {
                hard_links.push(HardLinkInfo {
                    link_path: full_path.clone(),
                    target_path: extract_dir.join(&link_name),
                    uid: original_uid,
                    gid: original_gid,
                    mode: original_mode,
                });
            }
            continue; // Skip to next entry
        }

        // Extract the entry (regular files, directories, symlinks)
        entry
            .unpack(&full_path)
            .map_err(|e| MicrosandboxError::LayerExtraction(format!("{:?}", e)))?;

        // Skip all operations for symlinks
        if is_symlink {
            tracing::trace!(
                "Extracted symlink {} with original uid:gid:mode {}:{}:{:o}",
                full_path.display(),
                original_uid,
                original_gid,
                original_mode
            );
            continue;
        }

        // For regular files and directories, handle permissions and xattrs
        let metadata = std::fs::metadata(&full_path)?;
        let is_dir = metadata.is_dir();
        let current_mode = metadata.permissions().mode();
        let current_permission_bits = current_mode & 0o7777; // Extract only permission bits

        // Calculate the final desired permissions
        let desired_permission_bits = if is_dir {
            // For directories, ensure at least u+rwx (0o700)
            current_permission_bits | 0o700
        } else {
            // For files, ensure at least u+rw (0o600)
            current_permission_bits | 0o600
        };

        // If we need to modify permissions, do it once
        if current_permission_bits != desired_permission_bits {
            let mut permissions = metadata.permissions();
            permissions.set_mode(desired_permission_bits);
            std::fs::set_permissions(&full_path, permissions)?;
        }

        // Store original uid/gid/mode in xattrs
        set_stat_xattr(&full_path, &xattr_name, original_uid, original_gid, original_mode)?;

        tracing::trace!(
            "Extracted {} with original uid:gid:mode {}:{}:{:o}, stored in xattr",
            full_path.display(),
            original_uid,
            original_gid,
            original_mode
        );
    }

    // Second pass: process hard links after all regular files are extracted
    for link_info in hard_links {
        // Create the hard link
        match std::fs::hard_link(&link_info.target_path, &link_info.link_path) {
            Ok(_) => {
                // Hard link created successfully, now handle xattrs
                // Get metadata and ensure proper permissions
                let metadata = match std::fs::metadata(&link_info.link_path) {
                    Ok(m) => m,
                    Err(e) => {
                        tracing::warn!(
                            "Failed to get metadata for hard link {}: {}",
                            link_info.link_path.display(),
                            e
                        );
                        continue;
                    }
                };

                let current_mode = metadata.permissions().mode();
                let current_permission_bits = current_mode & 0o7777; // Extract only permission bits
                let desired_permission_bits = current_permission_bits | 0o600; // Ensure at least u+rw

                // Set permissions if needed
                if current_permission_bits != desired_permission_bits {
                    let mut permissions = metadata.permissions();
                    permissions.set_mode(desired_permission_bits);
                    if let Err(e) = std::fs::set_permissions(&link_info.link_path, permissions) {
                        tracing::warn!(
                            "Failed to set permissions for hard link {}: {}",
                            link_info.link_path.display(),
                            e
                        );
                        continue;
                    }
                }

                // Store original uid/gid/mode in xattrs
                if let Err(e) = set_stat_xattr(&link_info.link_path, &xattr_name, link_info.uid, link_info.gid, link_info.mode) {
                    // For hard links, we just warn on xattr errors instead of failing
                    tracing::warn!("Failed to set xattr on hard link {}: {}", link_info.link_path.display(), e);
                }

                tracing::trace!(
                    "Created hard link {} -> {} with original uid:gid:mode {}:{}:{:o}",
                    link_info.link_path.display(),
                    link_info.target_path.display(),
                    link_info.uid,
                    link_info.gid,
                    link_info.mode
                );
            }
            Err(e) => {
                tracing::warn!(
                    "Failed to create hard link {} -> {}: {}",
                    link_info.link_path.display(),
                    link_info.target_path.display(),
                    e
                );
            }
        }
    }

    Ok(())
}

async fn extract_layer(
    layer_path: impl AsRef<Path>,
    extract_base_dir: impl AsRef<Path>,
) -> MicrosandboxResult<()> {
    let layer_path = layer_path.as_ref();
    let file_name = layer_path
        .file_name()
        .and_then(|n| n.to_str())
        .ok_or_else(|| MicrosandboxError::LayerHandling {
            source: std::io::Error::new(std::io::ErrorKind::NotFound, "invalid layer file name"),
            layer: layer_path.display().to_string(),
        })?;

    // Create the extraction directory with name <layer-name>.extracted
    let extract_dir = extract_base_dir
        .as_ref()
        .join(format!("{}.{}", file_name, EXTRACTED_LAYER_SUFFIX));

    // Check if the layer is already extracted
    if extract_dir.exists() {
        // Check if the directory has content (not empty)
        let mut read_dir =
            fs::read_dir(&extract_dir)
                .await
                .map_err(|e| MicrosandboxError::LayerHandling {
                    source: e,
                    layer: file_name.to_string(),
                })?;

        if read_dir.next_entry().await?.is_some() {
            tracing::info!(
                "layer {} already extracted at {}, skipping extraction",
                file_name,
                extract_dir.display()
            );
            return Ok(());
        }
    }

    fs::create_dir_all(&extract_dir)
        .await
        .map_err(|e| MicrosandboxError::LayerHandling {
            source: e,
            layer: file_name.to_string(),
        })?;

    tracing::info!(
        "extracting layer {} to {}",
        file_name,
        extract_dir.display()
    );

    #[cfg(feature = "cli")]
    struct ProgressReader<R> {
        inner: R,
        bar: ProgressBar,
    }

    #[cfg(feature = "cli")]
    impl<R: Read> Read for ProgressReader<R> {
        fn read(&mut self, buf: &mut [u8]) -> IoResult<usize> {
            let n = self.inner.read(buf)?;
            if n > 0 {
                self.bar.inc(n as u64);
            }
            Ok(n)
        }
    }

    #[cfg(feature = "cli")]
    {
        let total_bytes = fs::metadata(layer_path).await?.len();
        let pb = MULTI_PROGRESS.add(ProgressBar::new(total_bytes));
        pb.set_style(
            ProgressStyle::with_template(
                "{prefix:.bold.dim} {bar:40.green/green.dim} {bytes:.bold}/{total_bytes:.dim}",
            )
            .unwrap()
            .progress_chars("=+-"),
        );
        let digest_short = if let Some(rest) = file_name.strip_prefix("sha256:") {
            &rest[..8.min(rest.len())]
        } else {
            &file_name[..8.min(file_name.len())]
        };
        pb.set_prefix(format!("{}", digest_short));

        let layer_path_clone = layer_path.to_path_buf();
        let extract_dir_clone = extract_dir.clone();
        let pb_clone = pb.clone();

        spawn_blocking(move || -> MicrosandboxResult<()> {
            let file = std::fs::File::open(&layer_path_clone)?;
            let reader = ProgressReader {
                inner: file,
                bar: pb_clone.clone(),
            };
            let decoder = GzDecoder::new(reader);
            let mut archive = Archive::new(decoder);
            extract_tar_with_ownership_override(&mut archive, &extract_dir_clone)?;
            Ok(())
        })
        .await
        .map_err(|e| MicrosandboxError::LayerExtraction(format!("{:?}", e)))??;

        pb.finish_and_clear();
    }

    #[cfg(not(feature = "cli"))]
    {
        use flate2::read::GzDecoder;

        let file =
            std::fs::File::open(layer_path).map_err(|e| MicrosandboxError::LayerHandling {
                source: e,
                layer: file_name.to_string(),
            })?;
        let decoder = GzDecoder::new(file);
        let mut archive = Archive::new(decoder);
        extract_tar_with_ownership_override(&mut archive, &extract_dir)?;
    }

    tracing::info!(
        "successfully extracted layer {} to {}",
        file_name,
        extract_dir.display()
    );
    Ok(())
}

/// Collects all layer files in the given directory that start with "sha256:".
async fn collect_layer_files(dir: impl AsRef<Path>) -> MicrosandboxResult<Vec<PathBuf>> {
    let mut layer_paths = Vec::new();
    let mut read_dir = fs::read_dir(dir).await?;

    while let Ok(Some(entry)) = read_dir.next_entry().await {
        let path = entry.path();
        if path.is_file() {
            if let Some(file_name) = path.file_name().and_then(|n| n.to_str()) {
                if file_name.starts_with("sha256:") {
                    layer_paths.push(path.clone());
                }
            }
        }
    }

    tracing::info!("found {} layers to extract", layer_paths.len());
    Ok(layer_paths)
}

//--------------------------------------------------------------------------------------------------
// Tests
//--------------------------------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test_log::test(tokio::test)]
    #[ignore = "makes network requests to Docker registry to pull an image"]
    async fn test_image_pull_from_docker_registry() -> MicrosandboxResult<()> {
        // Create temporary directories for test
        let temp_dir = TempDir::new()?;
        let microsandbox_home = temp_dir.path().join("microsandbox_home");
        let download_dir = temp_dir.path().join("download");
        fs::create_dir_all(&microsandbox_home).await?;
        fs::create_dir_all(&download_dir).await?;

        // Set up test environment
        std::env::set_var("MICROSANDBOX_HOME", microsandbox_home.to_str().unwrap());

        // Create test image reference (using a small image for faster tests)
        let image_ref: Reference = "docker.io/library/nginx:stable-alpine".parse().unwrap();

        // Call the function under test
        pull_from_docker_registry(&image_ref, &download_dir, None).await?;

        // Initialize database connection for verification
        let db_path = microsandbox_home.join(OCI_DB_FILENAME);
        let pool = db::get_or_create_pool(&db_path, &OCI_DB_MIGRATOR).await?;

        // Verify image exists in database
        let image_exists = db::image_exists(&pool, &image_ref.to_string()).await?;
        assert!(image_exists, "Image should exist in database");

        // Verify layers directory exists and contains extracted layers
        let layers_dir = microsandbox_home.join(LAYERS_SUBDIR);
        assert!(layers_dir.exists(), "Layers directory should exist");

        // Verify extracted layer directories exist
        let mut entries = fs::read_dir(&layers_dir).await?;
        let mut found_extracted_layers = false;
        while let Some(entry) = entries.next_entry().await? {
            if entry
                .file_name()
                .to_string_lossy()
                .ends_with(EXTRACTED_LAYER_SUFFIX)
            {
                found_extracted_layers = true;
                assert!(
                    entry.path().is_dir(),
                    "Extracted layer path should be a directory"
                );
            }
        }
        assert!(
            found_extracted_layers,
            "Should have found extracted layer directories"
        );

        // Verify nginx files exist in the extracted layers
        helper::verify_nginx_files(&layers_dir).await?;

        Ok(())
    }
}

#[cfg(test)]
mod helper {
    use super::*;

    /// Helper function to verify that all expected nginx files exist in the extracted layers
    pub(super) async fn verify_nginx_files(layers_dir: impl AsRef<Path>) -> MicrosandboxResult<()> {
        let mut found_nginx_conf = false;
        let mut found_default_conf = false;
        let mut found_nginx_binary = false;

        // Check each extracted layer directory for nginx files
        let mut entries = fs::read_dir(layers_dir).await?;
        while let Some(entry) = entries.next_entry().await? {
            if !entry
                .file_name()
                .to_string_lossy()
                .ends_with(EXTRACTED_LAYER_SUFFIX)
            {
                continue;
            }

            let layer_path = entry.path();
            tracing::info!("checking layer: {}", layer_path.display());

            // Check for nginx.conf
            let nginx_conf = layer_path.join("etc").join("nginx").join("nginx.conf");
            if nginx_conf.exists() {
                found_nginx_conf = true;
                tracing::info!("found nginx.conf at {}", nginx_conf.display());
            }

            // Check for default.conf
            let default_conf = layer_path
                .join("etc")
                .join("nginx")
                .join("conf.d")
                .join("default.conf");
            if default_conf.exists() {
                found_default_conf = true;
                tracing::info!("found default.conf at {}", default_conf.display());
            }

            // Check for nginx binary
            let nginx_binary = layer_path.join("usr").join("sbin").join("nginx");
            if nginx_binary.exists() {
                found_nginx_binary = true;
                tracing::info!("found nginx binary at {}", nginx_binary.display());
            }

            // If we found all files, we can stop checking
            if found_nginx_conf && found_default_conf && found_nginx_binary {
                break;
            }
        }

        // Assert that we found all the expected files
        assert!(
            found_nginx_conf,
            "nginx.conf should exist in one of the layers"
        );
        assert!(
            found_default_conf,
            "default.conf should exist in one of the layers"
        );
        assert!(
            found_nginx_binary,
            "nginx binary should exist in one of the layers"
        );

        Ok(())
    }
}
