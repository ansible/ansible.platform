# Import role

Import Ansible Automation Platform Controller resources from a structured asset
mapping. The role applies resources in dependency order by using the
corresponding `ansible.platform` modules.

The role accepts the native asset format produced by the `export` module. It
can also convert legacy `awxkit` export data when
`import_controller_auto_convert_legacy` is enabled.

## Requirements

- Ansible Core 2.15 or later
- The `ansible.platform` collection
- Access to an AAP Controller or Gateway

## Role variables

- `import_controller_assets`: Mapping of resource-type names to lists of resource
  definitions. Defaults to `{}`.
- `import_controller_auto_convert_legacy`: Convert legacy `awxkit` export data with the
  `ansible.platform.from_awxkit_export` filter before importing. Defaults to
  `false`.
- `import_controller_state`: State passed to each resource module. Defaults to `present`.

## Example

```yaml
- name: Import Controller resources
  ansible.builtin.include_role:
    name: ansible.platform.import
  vars:
    import_controller_assets:
      organizations:
        - name: Default
          description: Default organization
      projects:
        - name: Example project
          organization: Default
          scm_type: git
          scm_url: https://example.com/example/project.git
    import_controller_state: present
```

To import a legacy `awxkit` export, provide the export under `import_controller_assets`
and set `import_controller_auto_convert_legacy: true`.
