# Architecture Diagrams

This directory contains diagram specifications for the Ansible Platform Collection architecture.

## Files

- **process_architecture.mmd** - Mermaid diagram (for GitHub, GitLab, etc.)
- **process_architecture.puml** - PlantUML diagram (for documentation tools)
- **process_architecture.dot** - Graphviz DOT format (for generating PNG/SVG)

## How to Generate Diagrams

### Mermaid (GitHub/GitLab)

Mermaid diagrams render automatically on GitHub and GitLab. Just include the `.mmd` file content in a markdown file:

```markdown
```mermaid
[content from process_architecture.mmd]
```
```

Or use online tools:
- https://mermaid.live/
- https://mermaid-js.github.io/mermaid-live-editor/

### PlantUML

1. Install PlantUML: http://plantuml.com/starting
2. Generate diagram:
   ```bash
   plantuml process_architecture.puml
   ```

Or use online tools:
- http://www.plantuml.com/plantuml/uml/
- VS Code extension: "PlantUML"

### Graphviz (DOT)

1. Install Graphviz: https://graphviz.org/download/
2. Generate diagram:
   ```bash
   dot -Tpng process_architecture.dot -o process_architecture.png
   dot -Tsvg process_architecture.dot -o process_architecture.svg
   ```

## Diagram Content

All diagrams show:
- **2 Processes**: Ansible Playbook Process + Manager Process
- **Threads**: Main thread + worker threads in Manager Process
- **Services**: PlatformService (shared instance)
- **Communication**: Unix Socket (RPC) and HTTP/HTTPS

## Key Points

1. **Manager Process** creates PlatformService (the sharable resource)
2. **PlatformManager** uses ThreadingMixIn for concurrent connections
3. **PlatformService** is shared via RPC proxy to all action plugins
4. **Persistent HTTP session** is reused across all tasks
