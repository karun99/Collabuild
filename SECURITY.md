# Security Policy

## Supported Versions

| Version | Supported          |
|---------|-------------------|
| 0.3.x   | Yes               |
| < 0.3   | No                |

## Reporting a Vulnerability

If you discover a security vulnerability within Collabuild MAS, please send an email to karun99@users.noreply.github.com. All security vulnerabilities will be promptly addressed.

**Please do NOT report security vulnerabilities through public GitHub issues.**

## Security Considerations

### API Keys

- Never commit `.env` files or API keys to version control
- Use environment variables or `config.yaml` with `${ENV_VAR}` syntax
- The `.gitignore` already excludes `.env` and `settings.json`

### Web UI

- The web UI binds to `127.0.0.1` by default — use `--host 0.0.0.0` only in trusted networks
- No authentication is built in — add a reverse proxy with auth for production
- CORS is not restricted by default — configure for your deployment

### Agent Runner

- The `python_exec` tool runs in a sandboxed `exec()` with limited builtins
- Do not expose the `/api/tools/agent-run` endpoint to untrusted users without additional sandboxing

### Docker

- Use Docker secrets or environment variables for API keys — never bake them into images
- The Dockerfile runs as root by default — consider adding a non-root user for production

## Best Practices

1. Use HTTPS in production (via reverse proxy like nginx/Caddy)
2. Add authentication (API keys, JWT, or OAuth) before exposing publicly
3. Set up rate limiting on API endpoints
4. Use Docker secrets for sensitive configuration
5. Regularly update dependencies: `pip install --upgrade`
