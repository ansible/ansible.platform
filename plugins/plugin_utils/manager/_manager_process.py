#!/usr/bin/env python3
"""
Standalone script for the persistent manager process.

This is executed as a separate process and doesn't rely on multiprocessing.spawn.
"""

import sys
import json
import base64
import traceback
from pathlib import Path


def main():
    """Main entry point for the manager process."""
    # Read configuration from command line args
    if len(sys.argv) < 2:
        print("ERROR: No config provided", file=sys.stderr)
        sys.exit(1)
    
    config_json = sys.argv[1]
    config = json.loads(config_json)
    
    socket_path = config['socket_path']
    socket_dir = config['socket_dir']
    inventory_hostname = config['inventory_hostname']
    gateway_url = config['gateway_url']
    gateway_username = config['gateway_username']
    gateway_password = config['gateway_password']
    gateway_token = config['gateway_token']
    gateway_validate_certs = config['gateway_validate_certs']
    gateway_request_timeout = config['gateway_request_timeout']
    authkey_b64 = config['authkey_b64']
    sys_path = config['sys_path']
    
    # Redirect stderr to a file for debugging
    stderr_log = Path(socket_dir) / f'manager_stderr_{inventory_hostname}.log'
    error_log = Path(socket_dir) / f'manager_error_{inventory_hostname}.log'
    
    try:
        sys.stderr = open(stderr_log, 'w', buffering=1)
        sys.stdout = open(stderr_log, 'a', buffering=1)
    except Exception:
        pass  # Continue without redirecting
    
    try:
        # Restore parent's sys.path in child process
        sys.path = sys_path
        
        # Decode authkey from base64
        authkey = base64.b64decode(authkey_b64)
        
        # Write to log immediately
        with open(error_log, 'w') as f:
            f.write(f"Process started, socket_path={socket_path}\n")
            f.write(f"sys.path has {len(sys_path)} entries\n")
            f.write(f"Manager starting at {socket_path}\n")
            f.write(f"About to create service with base_url={gateway_url}\n")
            f.flush()
        
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import (
            PlatformManager,
            PlatformService
        )
        
        with open(error_log, 'a') as f:
            f.write("Imports successful\n")
            f.flush()
        
        # Create service
        try:
            service = PlatformService(
                base_url=gateway_url,
                username=gateway_username,
                password=gateway_password,
                oauth_token=gateway_token,
                verify_ssl=gateway_validate_certs,
                request_timeout=gateway_request_timeout
            )
            with open(error_log, 'a') as f:
                f.write("Service created successfully\n")
                f.flush()
        except Exception as service_err:
            with open(error_log, 'a') as f:
                f.write(f"Service creation failed: {service_err}\n")
                f.write(traceback.format_exc())
                f.flush()
            raise
        
        with open(error_log, 'a') as f:
            f.write("Service created\n")
            f.flush()
        
        # Register with manager
        PlatformManager.register(
            'get_platform_service',
            callable=lambda: service
        )
        
        with open(error_log, 'a') as f:
            f.write("Service registered\n")
            f.flush()
        
        # Start manager server
        manager = PlatformManager(address=socket_path, authkey=authkey)
        
        with open(error_log, 'a') as f:
            f.write("Manager instance created\n")
            f.flush()
        
        server = manager.get_server()
        
        with open(error_log, 'a') as f:
            f.write("Server obtained, starting serve_forever()\n")
            f.flush()
        
        server.serve_forever()
        
    except Exception as e:
        # Log to a temp file for debugging
        with open(error_log, 'a') as f:
            f.write(f"\n\nManager startup failed: {e}\n")
            f.write(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()

