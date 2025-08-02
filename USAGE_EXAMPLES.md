# Usage Examples

This document provides comprehensive examples of using the microsandbox MCP server's simplified interface.

## Basic Code Execution

### Python Examples

#### Simple Python Script

```json
{
  "method": "tools/call",
  "params": {
    "name": "execute_code",
    "arguments": {
      "code": "print('Hello from Python sandbox!')\nprint(f'2 + 2 = {2 + 2}')",
      "template": "python"
    }
  }
}
```

**Response:**
```json
{
  "result": {
    "content": [{
      "type": "text",
      "text": "{\"session_id\":\"session-abc123\",\"stdout\":\"Hello from Python sandbox!\\n2 + 2 = 4\\n\",\"stderr\":\"\",\"exit_code\":null,\"execution_time_ms\":145,\"session_created\":true}"
    }]
  }
}
```

#### Data Processing with Pandas

```json
{
  "method": "tools/call",
  "params": {
    "name": "execute_code",
    "arguments": {
      "code": "import pandas as pd\nimport numpy as np\n\n# Create sample data\ndata = {'name': ['Alice', 'Bob', 'Charlie'], 'age': [25, 30, 35], 'city': ['NYC', 'LA', 'Chicago']}\ndf = pd.DataFrame(data)\n\nprint('Sample DataFrame:')\nprint(df)\nprint(f'\\nAverage age: {df[\"age\"].mean()}')",
      "template": "python",
      "flavor": "medium"
    }
  }
}
```

#### File Operations with Shared Volume

```json
{
  "method": "tools/call",
  "params": {
    "name": "execute_code",
    "arguments": {
      "code": "import os\n\n# Write to shared volume\nwith open('/shared/output.txt', 'w') as f:\n    f.write('Hello from Python sandbox!\\n')\n    f.write('This file is accessible from the host.\\n')\n\n# List shared directory contents\nprint('Files in shared directory:')\nfor item in os.listdir('/shared'):\n    print(f'  {item}')\n\nprint('\\nFile written successfully!')",
      "template": "python",
      "session_id": "my-python-session"
    }
  }
}
```

### Node.js Examples

#### Basic JavaScript

```json
{
  "method": "tools/call",
  "params": {
    "name": "execute_code",
    "arguments": {
      "code": "console.log('Hello from Node.js sandbox!');\nconst result = [1, 2, 3, 4, 5].reduce((sum, n) => sum + n, 0);\nconsole.log(`Sum of array: ${result}`);\nconsole.log(`Node.js version: ${process.version}`);",
      "template": "node"
    }
  }
}
```

#### Express Web Server

```json
{
  "method": "tools/call",
  "params": {
    "name": "execute_code",
    "arguments": {
      "code": "const express = require('express');\nconst app = express();\nconst port = 3000;\n\napp.get('/', (req, res) => {\n  res.json({ message: 'Hello from microsandbox!', timestamp: new Date().toISOString() });\n});\n\napp.get('/health', (req, res) => {\n  res.json({ status: 'healthy', uptime: process.uptime() });\n});\n\nconst server = app.listen(port, () => {\n  console.log(`Server running at http://localhost:${port}`);\n});\n\n// Stop server after 5 seconds for demo\nsetTimeout(() => {\n  server.close();\n  console.log('Server stopped');\n}, 5000);",
      "template": "node",
      "flavor": "medium"
    }
  }
}
```

#### Working with JSON Data

```json
{
  "method": "tools/call",
  "params": {
    "name": "execute_code",
    "arguments": {
      "code": "const fs = require('fs');\n\n// Sample data\nconst users = [\n  { id: 1, name: 'Alice', email: 'alice@example.com' },\n  { id: 2, name: 'Bob', email: 'bob@example.com' },\n  { id: 3, name: 'Charlie', email: 'charlie@example.com' }\n];\n\n// Write to shared volume\nfs.writeFileSync('/shared/users.json', JSON.stringify(users, null, 2));\nconsole.log('Users data written to /shared/users.json');\n\n// Process data\nconst emailDomains = users.map(u => u.email.split('@')[1]);\nconst uniqueDomains = [...new Set(emailDomains)];\nconsole.log('Unique email domains:', uniqueDomains);",
      "template": "node"
    }
  }
}
```

## Command Execution

### System Information

```json
{
  "method": "tools/call",
  "params": {
    "name": "execute_command",
    "arguments": {
      "command": "uname",
      "args": ["-a"],
      "template": "python"
    }
  }
}
```

### File System Operations

```json
{
  "method": "tools/call",
  "params": {
    "name": "execute_command",
    "arguments": {
      "command": "ls",
      "args": ["-la", "/shared"],
      "template": "python"
    }
  }
}
```

### Network Operations

```json
{
  "method": "tools/call",
  "params": {
    "name": "execute_command",
    "arguments": {
      "command": "curl",
      "args": ["-s", "https://api.github.com/users/octocat"],
      "template": "python"
    }
  }
}
```

### Package Installation

```json
{
  "method": "tools/call",
  "params": {
    "name": "execute_command",
    "arguments": {
      "command": "pip",
      "args": ["install", "requests"],
      "template": "python",
      "session_id": "my-python-session"
    }
  }
}
```

## Session Management

### List Active Sessions

```json
{
  "method": "tools/call",
  "params": {
    "name": "get_sessions"
  }
}
```

**Response:**
```json
{
  "result": {
    "content": [{
      "type": "text",
      "text": "{\"sessions\":[{\"id\":\"session-abc123\",\"language\":\"python\",\"flavor\":\"small\",\"status\":\"ready\",\"created_at\":\"2024-01-15T10:30:00Z\",\"last_accessed\":\"2024-01-15T10:35:00Z\",\"uptime_seconds\":300}]}"
    }]
  }
}
```

### Get Specific Session Info

```json
{
  "method": "tools/call",
  "params": {
    "name": "get_sessions",
    "arguments": {
      "session_id": "session-abc123"
    }
  }
}
```

### Stop a Session

```json
{
  "method": "tools/call",
  "params": {
    "name": "stop_session",
    "arguments": {
      "session_id": "session-abc123"
    }
  }
}
```

### Get Shared Volume Path

```json
{
  "method": "tools/call",
  "params": {
    "name": "get_volume_path"
  }
}
```

**Response:**
```json
{
  "result": {
    "content": [{
      "type": "text",
      "text": "{\"volume_path\":\"/shared\",\"description\":\"Shared volume for file exchange between host and sandbox\",\"available\":true}"
    }]
  }
}
```

## Advanced Workflows

### Multi-Step Data Analysis

```json
// Step 1: Create dataset
{
  "method": "tools/call",
  "params": {
    "name": "execute_code",
    "arguments": {
      "code": "import pandas as pd\nimport numpy as np\n\n# Generate sample sales data\nnp.random.seed(42)\ndates = pd.date_range('2024-01-01', periods=100, freq='D')\nsales = np.random.normal(1000, 200, 100)\ndata = pd.DataFrame({'date': dates, 'sales': sales})\n\n# Save to shared volume\ndata.to_csv('/shared/sales_data.csv', index=False)\nprint(f'Generated {len(data)} sales records')\nprint(data.head())",
      "template": "python",
      "flavor": "medium",
      "session_id": "analysis-session"
    }
  }
}

// Step 2: Analyze data
{
  "method": "tools/call",
  "params": {
    "name": "execute_code",
    "arguments": {
      "code": "import pandas as pd\nimport matplotlib.pyplot as plt\n\n# Load data\ndata = pd.read_csv('/shared/sales_data.csv')\ndata['date'] = pd.to_datetime(data['date'])\n\n# Calculate statistics\nstats = {\n    'total_sales': data['sales'].sum(),\n    'avg_daily_sales': data['sales'].mean(),\n    'max_sales': data['sales'].max(),\n    'min_sales': data['sales'].min()\n}\n\nprint('Sales Analysis:')\nfor key, value in stats.items():\n    print(f'  {key}: ${value:,.2f}')\n\n# Create visualization\nplt.figure(figsize=(12, 6))\nplt.plot(data['date'], data['sales'])\nplt.title('Daily Sales Trend')\nplt.xlabel('Date')\nplt.ylabel('Sales ($)')\nplt.xticks(rotation=45)\nplt.tight_layout()\nplt.savefig('/shared/sales_trend.png')\nprint('\\nChart saved to /shared/sales_trend.png')",
      "template": "python",
      "session_id": "analysis-session"
    }
  }
}
```

### Cross-Language Workflow

```json
// Step 1: Generate data with Python
{
  "method": "tools/call",
  "params": {
    "name": "execute_code",
    "arguments": {
      "code": "import json\nimport random\n\n# Generate API response data\napi_data = {\n    'users': [\n        {'id': i, 'name': f'User{i}', 'score': random.randint(50, 100)}\n        for i in range(1, 11)\n    ],\n    'metadata': {\n        'total': 10,\n        'generated_at': '2024-01-15T10:00:00Z'\n    }\n}\n\n# Save for Node.js processing\nwith open('/shared/api_data.json', 'w') as f:\n    json.dump(api_data, f, indent=2)\n\nprint('Generated API data with 10 users')\nprint(f'Average score: {sum(u[\"score\"] for u in api_data[\"users\"]) / len(api_data[\"users\"]):.1f}')",
      "template": "python",
      "session_id": "python-session"
    }
  }
}

// Step 2: Process with Node.js
{
  "method": "tools/call",
  "params": {
    "name": "execute_code",
    "arguments": {
      "code": "const fs = require('fs');\n\n// Read Python-generated data\nconst rawData = fs.readFileSync('/shared/api_data.json', 'utf8');\nconst apiData = JSON.parse(rawData);\n\n// Process data\nconst highScorers = apiData.users.filter(user => user.score >= 80);\nconst report = {\n    total_users: apiData.users.length,\n    high_scorers: highScorers.length,\n    high_scorer_names: highScorers.map(u => u.name),\n    average_score: apiData.users.reduce((sum, u) => sum + u.score, 0) / apiData.users.length\n};\n\n// Save report\nfs.writeFileSync('/shared/report.json', JSON.stringify(report, null, 2));\n\nconsole.log('Processing Report:');\nconsole.log(`Total users: ${report.total_users}`);\nconsole.log(`High scorers (≥80): ${report.high_scorers}`);\nconsole.log(`Names: ${report.high_scorer_names.join(', ')}`);\nconsole.log(`Average score: ${report.average_score.toFixed(1)}`);\nconsole.log('\\nReport saved to /shared/report.json');",
      "template": "node",
      "session_id": "node-session"
    }
  }
}
```

### Web Scraping and Analysis

```json
// Step 1: Install dependencies
{
  "method": "tools/call",
  "params": {
    "name": "execute_command",
    "arguments": {
      "command": "pip",
      "args": ["install", "requests", "beautifulsoup4"],
      "template": "python",
      "session_id": "scraping-session"
    }
  }
}

// Step 2: Scrape data
{
  "method": "tools/call",
  "params": {
    "name": "execute_code",
    "arguments": {
      "code": "import requests\nfrom bs4 import BeautifulSoup\nimport json\n\n# Example: Get GitHub trending repositories\nurl = 'https://api.github.com/search/repositories?q=language:python&sort=stars&order=desc&per_page=10'\nheaders = {'Accept': 'application/vnd.github.v3+json'}\n\nresponse = requests.get(url, headers=headers)\ndata = response.json()\n\n# Extract relevant information\nrepos = []\nfor item in data['items']:\n    repos.append({\n        'name': item['name'],\n        'full_name': item['full_name'],\n        'stars': item['stargazers_count'],\n        'description': item['description'][:100] if item['description'] else 'No description',\n        'language': item['language'],\n        'url': item['html_url']\n    })\n\n# Save data\nwith open('/shared/github_repos.json', 'w') as f:\n    json.dump(repos, f, indent=2)\n\nprint(f'Scraped {len(repos)} repositories:')\nfor repo in repos[:5]:\n    print(f'  {repo[\"full_name\"]} - {repo[\"stars\"]} stars')",
      "template": "python",
      "session_id": "scraping-session",
      "flavor": "medium"
    }
  }
}
```

## Error Handling Examples

### Handling Session Errors

```json
// This will create a new session if the specified one doesn't exist
{
  "method": "tools/call",
  "params": {
    "name": "execute_code",
    "arguments": {
      "code": "print('This will work even if session_id is invalid')",
      "template": "python",
      "session_id": "non-existent-session"
    }
  }
}
```

### Resource Management

```json
// Use small flavor for simple tasks
{
  "method": "tools/call",
  "params": {
    "name": "execute_code",
    "arguments": {
      "code": "print('Simple task with minimal resources')",
      "template": "python",
      "flavor": "small"
    }
  }
}

// Use large flavor for intensive tasks
{
  "method": "tools/call",
  "params": {
    "name": "execute_code",
    "arguments": {
      "code": "import numpy as np\n# Large matrix operations\nmatrix = np.random.rand(1000, 1000)\nresult = np.linalg.inv(matrix)\nprint(f'Computed inverse of {matrix.shape} matrix')",
      "template": "python",
      "flavor": "large"
    }
  }
}
```

## Integration Examples

### MCP Client Configuration

For Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "microsandbox": {
      "command": "curl",
      "args": ["-X", "POST", "http://localhost:5555/mcp"],
      "env": {}
    }
  }
}
```

### Programmatic Usage (Python)

```python
import requests
import json

class MicrosandboxClient:
    def __init__(self, base_url="http://localhost:5555"):
        self.base_url = base_url
        self.mcp_url = f"{base_url}/mcp"
    
    def execute_code(self, code, template="python", session_id=None, flavor="small"):
        payload = {
            "method": "tools/call",
            "params": {
                "name": "execute_code",
                "arguments": {
                    "code": code,
                    "template": template,
                    "flavor": flavor
                }
            }
        }
        
        if session_id:
            payload["params"]["arguments"]["session_id"] = session_id
        
        response = requests.post(self.mcp_url, json=payload)
        return response.json()
    
    def get_sessions(self):
        payload = {
            "method": "tools/call",
            "params": {
                "name": "get_sessions"
            }
        }
        
        response = requests.post(self.mcp_url, json=payload)
        return response.json()

# Usage
client = MicrosandboxClient()

# Execute Python code
result = client.execute_code("print('Hello from Python!')")
print(result)

# List sessions
sessions = client.get_sessions()
print(sessions)
```

These examples demonstrate the flexibility and power of the microsandbox simplified MCP interface for various use cases, from simple code execution to complex multi-step workflows.