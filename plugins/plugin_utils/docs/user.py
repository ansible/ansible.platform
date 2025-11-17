"""
DOCUMENTATION string for user module.

This serves as the single source of truth for the module's interface.
"""

DOCUMENTATION = """
---
module: user
author: Sean Sullivan (@sean-m-sullivan)
short_description: Manage gateway users
description:
  - Create, update, or delete users in Ansible Automation Platform Gateway
  - This module uses the persistent connection manager for improved performance
version_added: "1.0.0"

options:
  username:
    description:
      - Username for the user
      - Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.
    required: true
    type: str
    
  email:
    description:
      - Email address of the user
    type: str
    
  first_name:
    description:
      - First name of the user
    type: str
    
  last_name:
    description:
      - Last name of the user
    type: str
    
  password:
    description:
      - Password for the user
      - Write-only field used to set or change the password
    type: str
    no_log: true
    
  is_superuser:
    description:
      - Whether this user has superuser privileges
      - Grants all permissions without explicitly assigning them
    type: bool
    aliases: ['superuser']
    
  is_platform_auditor:
    description:
      - Whether this user is a platform auditor
      - Deprecated - use role_user_assignment module instead
    type: bool
    aliases: ['auditor']
    
  organizations:
    description:
      - List of organization names to associate with the user
      - Organizations must already exist
      - Deprecated - use role_user_assignment module instead
    type: list
    elements: str
    
  state:
    description:
      - Desired state of the user
    type: str
    choices: ['present', 'absent']
    default: 'present'
    
  gateway_hostname:
    description:
      - Gateway hostname
    type: str
    
  gateway_username:
    description:
      - Gateway username for authentication
    type: str
    
  gateway_password:
    description:
      - Gateway password for authentication
    type: str
    no_log: true
    
  gateway_token:
    description:
      - OAuth token for authentication
    type: str
    no_log: true
    
  gateway_validate_certs:
    description:
      - Whether to validate SSL certificates
    type: bool
    default: true
    
  gateway_request_timeout:
    description:
      - Request timeout in seconds
    type: float
    default: 10.0

notes:
  - This module uses a persistent connection manager for improved performance
  - Multiple tasks in a playbook will reuse the same connection
  - The organizations and is_platform_auditor fields are deprecated
  - Authentication requires either gateway_username/gateway_password or gateway_token
"""

