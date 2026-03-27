# Test Playbooks for Ansible Platform Collection

This document lists all available test playbooks you can run to test the Ansible Platform Collection.

## Prerequisites

Before running any playbooks, you need:

1. **A running Ansible Automation Platform (AAP) Gateway instance**
2. **Gateway credentials** (hostname, username, password)
3. **Ansible installed** (ansible-core >= 2.16.0, Python >= 3.11)

## Configuration

Set these variables when running playbooks (via `-e` flags, inventory, or environment variables):

```yaml
gateway_hostname: "https://your-gateway.example.com"
gateway_username: "admin"
gateway_password: "your-password"
gateway_validate_certs: false  # Set to true for production
```

## Running Playbooks

### Option 1: Using ansible-playbook directly

```bash
cd /Users/rohit/dev-workspace/ansible-dev/ansible_collections/ansible/platform

ansible-playbook tests/integration/targets/users_test/tasks/main.yml \
  -e gateway_hostname=https://your-gateway.example.com \
  -e gateway_username=admin \
  -e gateway_password=your-password \
  -e gateway_validate_certs=false
```

### Option 2: Using ansible-test integration

```bash
cd /Users/rohit/dev-workspace/ansible-dev/ansible_collections/ansible/platform

ansible-test integration --target users_test \
  -e gateway_hostname=https://your-gateway.example.com \
  -e gateway_username=admin \
  -e gateway_password=your-password \
  -e gateway_validate_certs=false
```

### Option 3: Using the main gateway test playbook

```bash
cd /Users/rohit/dev-workspace/ansible-dev/ansible_collections/ansible/platform

ansible-playbook tests/gateway_test.yml \
  -e gateway_host=https://your-gateway.example.com \
  -e gateway_admin_user=admin \
  -e gateway_admin_password=your-password
```

## Available Test Playbooks

### Core Resource Tests

#### 1. Users Test
**Location**: `tests/integration/targets/users_test/tasks/main.yml`

Tests user management including:
- Creating users with check mode
- Creating users with organizations
- Updating user properties (superuser, auditor flags)
- Modifying users by ID
- Deleting users
- Testing idempotency
- Testing associated authenticators
- Testing deprecation warnings

**Run**:
```bash
ansible-playbook tests/integration/targets/users_test/tasks/main.yml \
  -e gateway_hostname=YOUR_HOSTNAME \
  -e gateway_username=YOUR_USERNAME \
  -e gateway_password=YOUR_PASSWORD \
  -e gateway_validate_certs=false
```

#### 2. Organizations Test
**Location**: `tests/integration/targets/organizations_test/tasks/main.yml`

Tests organization management including:
- Creating organizations with check mode
- Creating and recreating organizations
- Modifying organizations by ID
- Renaming organizations
- Deleting organizations
- Testing idempotency

**Run**:
```bash
ansible-playbook tests/integration/targets/organizations_test/tasks/main.yml \
  -e gateway_hostname=YOUR_HOSTNAME \
  -e gateway_username=YOUR_USERNAME \
  -e gateway_password=YOUR_PASSWORD \
  -e gateway_validate_certs=false
```

#### 3. Teams Test
**Location**: `tests/integration/targets/teams_test/tasks/main.yml`

Tests team management including:
- Creating teams with organizations (by name and ID)
- Validating team creation requirements
- Updating team descriptions
- Renaming teams
- Changing team organizations
- Deleting teams
- Testing idempotency

**Run**:
```bash
ansible-playbook tests/integration/targets/teams_test/tasks/main.yml \
  -e gateway_hostname=YOUR_HOSTNAME \
  -e gateway_username=YOUR_USERNAME \
  -e gateway_password=YOUR_PASSWORD \
  -e gateway_validate_certs=false
```

### Role Assignment Tests

#### 4. Role User Assignments Test
**Location**: `tests/integration/targets/role_user_assignments_test/tasks/main.yml`

Tests assigning roles to users including:
- Creating users and organizations
- Assigning organization admin roles
- Testing role assignments with different identifiers

**Run**:
```bash
ansible-playbook tests/integration/targets/role_user_assignments_test/tasks/main.yml \
  -e gateway_hostname=YOUR_HOSTNAME \
  -e gateway_username=YOUR_USERNAME \
  -e gateway_password=YOUR_PASSWORD \
  -e gateway_validate_certs=false
```

#### 5. Role Team Assignments Test
**Location**: `tests/integration/targets/role_team_assignments_test/tasks/main.yml`

Tests assigning roles to teams including:
- Creating multiple organizations and teams
- Assigning roles to teams
- Testing role assignments

**Run**:
```bash
ansible-playbook tests/integration/targets/role_team_assignments_test/tasks/main.yml \
  -e gateway_hostname=YOUR_HOSTNAME \
  -e gateway_username=YOUR_USERNAME \
  -e gateway_password=YOUR_PASSWORD \
  -e gateway_validate_certs=false
```

### Application and Authentication Tests

#### 6. Applications Test
**Location**: `tests/integration/targets/applications_test/tasks/main.yml`

Tests application management including:
- Creating applications with organizations
- Testing application creation with check mode
- Managing application configurations

**Run**:
```bash
ansible-playbook tests/integration/targets/applications_test/tasks/main.yml \
  -e gateway_hostname=YOUR_HOSTNAME \
  -e gateway_username=YOUR_USERNAME \
  -e gateway_password=YOUR_PASSWORD \
  -e gateway_validate_certs=false
```

#### 7. Authenticators Test
**Location**: `tests/integration/targets/authenticators_test/tasks/main.yml`

Tests authenticator management.

**Run**:
```bash
ansible-playbook tests/integration/targets/authenticators_test/tasks/main.yml \
  -e gateway_hostname=YOUR_HOSTNAME \
  -e gateway_username=YOUR_USERNAME \
  -e gateway_password=YOUR_PASSWORD \
  -e gateway_validate_certs=false
```

#### 8. Authenticator Maps Test
**Location**: `tests/integration/targets/authenticator_maps_test/tasks/main.yml`

Tests authenticator map management.

**Run**:
```bash
ansible-playbook tests/integration/targets/authenticator_maps_test/tasks/main.yml \
  -e gateway_hostname=YOUR_HOSTNAME \
  -e gateway_username=YOUR_USERNAME \
  -e gateway_password=YOUR_PASSWORD \
  -e gateway_validate_certs=false
```

### Service Management Tests

#### 9. Services Test
**Location**: `tests/integration/targets/services_test/tasks/main.yml`

Tests service management.

**Run**:
```bash
ansible-playbook tests/integration/targets/services_test/tasks/main.yml \
  -e gateway_hostname=YOUR_HOSTNAME \
  -e gateway_username=YOUR_USERNAME \
  -e gateway_password=YOUR_PASSWORD \
  -e gateway_validate_certs=false
```

#### 10. Service Clusters Test
**Location**: `tests/integration/targets/service_clusters_test/tasks/main.yml`

Tests service cluster management.

**Run**:
```bash
ansible-playbook tests/integration/targets/service_clusters_test/tasks/main.yml \
  -e gateway_hostname=YOUR_HOSTNAME \
  -e gateway_username=YOUR_USERNAME \
  -e gateway_password=YOUR_PASSWORD \
  -e gateway_validate_certs=false
```

#### 11. Service Nodes Test
**Location**: `tests/integration/targets/service_nodes_test/tasks/main.yml`

Tests service node management.

**Run**:
```bash
ansible-playbook tests/integration/targets/service_nodes_test/tasks/main.yml \
  -e gateway_hostname=YOUR_HOSTNAME \
  -e gateway_username=YOUR_USERNAME \
  -e gateway_password=YOUR_PASSWORD \
  -e gateway_validate_certs=false
```

#### 12. Service Keys Test
**Location**: `tests/integration/targets/service_keys_test/tasks/main.yml`

Tests service key management.

**Run**:
```bash
ansible-playbook tests/integration/targets/service_keys_test/tasks/main.yml \
  -e gateway_hostname=YOUR_HOSTNAME \
  -e gateway_username=YOUR_USERNAME \
  -e gateway_password=YOUR_PASSWORD \
  -e gateway_validate_certs=false
```

#### 13. Service Types Test
**Location**: `tests/integration/targets/service_types_test/tasks/main.yml`

Tests service type management.

**Run**:
```bash
ansible-playbook tests/integration/targets/service_types_test/tasks/main.yml \
  -e gateway_hostname=YOUR_HOSTNAME \
  -e gateway_username=YOUR_USERNAME \
  -e gateway_password=YOUR_PASSWORD \
  -e gateway_validate_certs=false
```

### Other Resource Tests

#### 14. Routes Test
**Location**: `tests/integration/targets/routes_test/tasks/main.yml`

Tests route management.

**Run**:
```bash
ansible-playbook tests/integration/targets/routes_test/tasks/main.yml \
  -e gateway_hostname=YOUR_HOSTNAME \
  -e gateway_username=YOUR_USERNAME \
  -e gateway_password=YOUR_PASSWORD \
  -e gateway_validate_certs=false
```

#### 15. Role Definitions Test
**Location**: `tests/integration/targets/role_definitions_test/tasks/main.yml`

Tests role definition management.

**Run**:
```bash
ansible-playbook tests/integration/targets/role_definitions_test/tasks/main.yml \
  -e gateway_hostname=YOUR_HOSTNAME \
  -e gateway_username=YOUR_USERNAME \
  -e gateway_password=YOUR_PASSWORD \
  -e gateway_validate_certs=false
```

#### 16. Settings Test
**Location**: `tests/integration/targets/settings_test/tasks/main.yml`

Tests settings management.

**Run**:
```bash
ansible-playbook tests/integration/targets/settings_test/tasks/main.yml \
  -e gateway_hostname=YOUR_HOSTNAME \
  -e gateway_username=YOUR_USERNAME \
  -e gateway_password=YOUR_PASSWORD \
  -e gateway_validate_certs=false
```

#### 17. Tokens Test
**Location**: `tests/integration/targets/tokens_test/tasks/main.yml`

Tests token management.

**Run**:
```bash
ansible-playbook tests/integration/targets/tokens_test/tasks/main.yml \
  -e gateway_hostname=YOUR_HOSTNAME \
  -e gateway_username=YOUR_USERNAME \
  -e gateway_password=YOUR_PASSWORD \
  -e gateway_validate_certs=false
```

#### 18. CA Certificates Test
**Location**: `tests/integration/targets/ca_certificates_test/tasks/main.yml`

Tests CA certificate management.

**Run**:
```bash
ansible-playbook tests/integration/targets/ca_certificates_test/tasks/main.yml \
  -e gateway_hostname=YOUR_HOSTNAME \
  -e gateway_username=YOUR_USERNAME \
  -e gateway_password=YOUR_PASSWORD \
  -e gateway_validate_certs=false
```

#### 19. HTTP Ports Test
**Location**: `tests/integration/targets/http_ports_test/tasks/main.yml`

Tests HTTP port management.

**Run**:
```bash
ansible-playbook tests/integration/targets/http_ports_test/tasks/main.yml \
  -e gateway_hostname=YOUR_HOSTNAME \
  -e gateway_username=YOUR_USERNAME \
  -e gateway_password=YOUR_PASSWORD \
  -e gateway_validate_certs=false
```

#### 20. UI Plugin Routes Test
**Location**: `tests/integration/targets/ui_plugin_routes_test/tasks/main.yml`

Tests UI plugin route management.

**Run**:
```bash
ansible-playbook tests/integration/targets/ui_plugin_routes_test/tasks/main.yml \
  -e gateway_hostname=YOUR_HOSTNAME \
  -e gateway_username=YOUR_USERNAME \
  -e gateway_password=YOUR_PASSWORD \
  -e gateway_validate_certs=false
```

### Utility Tests

#### 21. Lookup Test
**Location**: `tests/integration/targets/lookup_test/tasks/main.yml`

Tests the `ansible.platform.gateway_api` lookup plugin (collection name is `ansible.platform`).

**Run**:
```bash
ansible-playbook tests/integration/targets/lookup_test/tasks/main.yml \
  -e gateway_hostname=YOUR_HOSTNAME \
  -e gateway_username=YOUR_USERNAME \
  -e gateway_password=YOUR_PASSWORD \
  -e gateway_validate_certs=false
```

## Main Gateway Test Playbook

**Location**: `tests/gateway_test.yml`

This is a comprehensive playbook that can run multiple test suites. Currently, most test includes are commented out, but you can uncomment them to run all tests together.

**Run**:
```bash
ansible-playbook tests/gateway_test.yml \
  -e gateway_host=https://your-gateway.example.com \
  -e gateway_admin_user=admin \
  -e gateway_admin_password=your-password
```

## Quick Start Examples

### Example 1: Test User Management

```bash
cd /Users/rohit/dev-workspace/ansible-dev/ansible_collections/ansible/platform

ansible-playbook tests/integration/targets/users_test/tasks/main.yml \
  -e gateway_hostname=https://localhost:8000 \
  -e gateway_username=admin \
  -e gateway_password=admin \
  -e gateway_validate_certs=false
```

### Example 2: Test Organization Management

```bash
cd /Users/rohit/dev-workspace/ansible-dev/ansible_collections/ansible/platform

ansible-playbook tests/integration/targets/organizations_test/tasks/main.yml \
  -e gateway_hostname=https://localhost:8000 \
  -e gateway_username=admin \
  -e gateway_password=admin \
  -e gateway_validate_certs=false
```

### Example 3: Test Team Management

```bash
cd /Users/rohit/dev-workspace/ansible-dev/ansible_collections/ansible/platform

ansible-playbook tests/integration/targets/teams_test/tasks/main.yml \
  -e gateway_hostname=https://localhost:8000 \
  -e gateway_username=admin \
  -e gateway_password=admin \
  -e gateway_validate_certs=false
```

## Using an Inventory File

The collection includes an `inventory` file at the root. You can add gateway variables to it or create a separate inventory file.

**Option 1: Use the existing inventory file**

Edit `inventory` to add variables:
```ini
[localhost]
127.0.0.1 gateway_hostname=https://your-gateway.example.com gateway_username=admin gateway_password=your-password gateway_validate_certs=false
```

Then run:
```bash
ansible-playbook tests/integration/targets/users_test/tasks/main.yml
```

**Option 2: Create a separate inventory file**

Create `inventory.yml`:
```yaml
all:
  hosts:
    localhost:
      vars:
        gateway_hostname: "https://your-gateway.example.com"
        gateway_username: "admin"
        gateway_password: "your-password"
        gateway_validate_certs: false
```

Then run:
```bash
ansible-playbook tests/integration/targets/users_test/tasks/main.yml -i inventory.yml
```

**Note**: The `ansible.cfg` file in the collection root is already configured to use the `inventory` file by default, so if you update that file, you don't need to specify `-i` flag.

## Notes

- All test playbooks automatically generate unique test IDs to avoid conflicts
- Test playbooks include cleanup tasks to remove created resources
- Most tests include assertions to verify expected behavior
- Check mode is tested in several playbooks to verify idempotency
- The tests are designed to be run against a development/test environment

## Troubleshooting

If you encounter connection issues:

1. **Verify Gateway is Running**: Use the setup playbook to check:
   ```bash
   ansible-playbook tests/integration/targets/setup_gateway/tasks/main.yml \
     -e gateway_hostname=YOUR_HOSTNAME \
     -e gateway_username=YOUR_USERNAME \
     -e gateway_password=YOUR_PASSWORD
   ```

2. **Check Certificate Validation**: If using self-signed certificates, set `gateway_validate_certs: false`

3. **Verify Credentials**: Ensure your username and password are correct

4. **Check Network Connectivity**: Verify you can reach the gateway hostname from your machine

