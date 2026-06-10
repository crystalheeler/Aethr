# Security Considerations

Aethr is designed as a **local signal intelligence tool** for personal use on trusted networks. This document outlines security considerations and best practices.

## Network Binding

By default, Aethr binds to `0.0.0.0:6969`, making it accessible from any network interface. This is convenient for accessing the web UI from other devices on your local network, but has security implications:

### Recommendations

1. **Firewall Rules**: If you don't need remote access, configure your firewall to block external access to port 6969:
   ```bash
   # Linux (iptables)
   sudo iptables -A INPUT -p tcp --dport 6969 -s 127.0.0.1 -j ACCEPT
   sudo iptables -A INPUT -p tcp --dport 6969 -j DROP

   # macOS (pf)
   echo "block in on en0 proto tcp from any to any port 6969" | sudo pfctl -ef -
   ```

2. **Bind to Localhost**: For local-only access, set the host or use the CLI flag:
   ```bash
   sudo ./start.sh -H 127.0.0.1
   ```

3. **Trusted Networks Only**: Only run Aethr on networks you trust. The application has no authentication mechanism.

## Authentication

Aethr does **not** include authentication. This is by design for ease of use as a personal tool. If you need to expose Aethr to untrusted networks:

1. Use a reverse proxy (nginx, Caddy) with authentication
2. Use a VPN to access your home network
3. Use SSH port forwarding: `ssh -L 6969:localhost:6969 your-server`

## Security Headers

Aethr includes the following security headers on all responses:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME type sniffing |
| `X-Frame-Options` | `SAMEORIGIN` | Prevent clickjacking |
| `X-XSS-Protection` | `1; mode=block` | Enable browser XSS filter |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Control referrer information |
| `Permissions-Policy` | `geolocation=(self), microphone=()` | Restrict browser features |

## Input Validation

All user inputs are validated before use:

- **Network interface names**: Validated against strict regex pattern
- **Bluetooth interface names**: Must match `hciX` format
- **MAC addresses**: Validated format
- **Frequencies**: Validated range and format
- **File paths**: Protected against directory traversal
- **HTML output**: All user-provided content is escaped

## Subprocess Execution

Aethr executes external tools (rtl_fm, airodump-ng, etc.) via subprocess. Security measures:

- **No shell execution**: All subprocess calls use list arguments, not shell strings
- **Input validation**: All user-provided arguments are validated before use
- **Process isolation**: Each tool runs in its own process with limited permissions

## Debug Mode

Debug mode is **disabled by default**. If enabled via `INTERCEPT_DEBUG=true`:

- The Werkzeug debugger PIN is disabled (not needed for local tool)
- Additional logging is enabled
- Stack traces are shown on errors

**Never run in debug mode on untrusted networks.**

## Reporting Security Issues

If you discover a security vulnerability, please report it by:

1. Opening a GitHub issue (for non-sensitive issues)
2. Emailing the maintainer directly (for sensitive issues)

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)
