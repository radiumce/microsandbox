#!/usr/bin/env python3
"""
Setup script for HTTP Streamable MCP Server for Microsandbox

This setup script allows the MCP server to be installed as a Python package
for easier deployment and distribution.
"""

from setuptools import setup, find_packages
import os

# Read the README file for long description
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "HTTP Streamable MCP Server for Microsandbox"

# Read requirements from requirements.txt
def read_requirements():
    requirements_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    requirements = []
    if os.path.exists(requirements_path):
        with open(requirements_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith('#'):
                    # Remove inline comments
                    if '#' in line:
                        line = line.split('#')[0].strip()
                    requirements.append(line)
    return requirements

setup(
    name="mcp-server-microsandbox",
    version="1.0.0",
    description="HTTP Streamable MCP Server for Microsandbox",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="Microsandbox Team",
    author_email="support@microsandbox.io",
    url="https://github.com/microsandbox/microsandbox",
    
    # Package configuration
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.8",
    
    # Dependencies
    install_requires=read_requirements(),
    
    # Entry points for command-line usage
    entry_points={
        'console_scripts': [
            'mcp-server=mcp_server.main:main',
        ],
    },
    
    # Package metadata
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: System :: Distributed Computing",
    ],
    
    # Keywords for PyPI
    keywords="mcp model-context-protocol microsandbox sandbox http-server",
    
    # Project URLs
    project_urls={
        "Bug Reports": "https://github.com/microsandbox/microsandbox/issues",
        "Source": "https://github.com/microsandbox/microsandbox",
        "Documentation": "https://github.com/microsandbox/microsandbox/tree/main/mcp-server",
    },
    
    # Additional package data
    package_data={
        'mcp_server': [
            '*.md',
            '*.txt',
            '*.yml',
            '*.yaml',
        ],
    },
    
    # Extras for optional dependencies
    extras_require={
        'dev': [
            'black>=22.0.0',
            'flake8>=5.0.0',
            'mypy>=1.0.0',
            'pytest>=7.0.0',
            'pytest-asyncio>=0.21.0',
            'pytest-mock>=3.10.0',
        ],
        'test': [
            'pytest>=7.0.0',
            'pytest-asyncio>=0.21.0',
            'pytest-mock>=3.10.0',
        ],
    },
    
    # Zip safety
    zip_safe=False,
)