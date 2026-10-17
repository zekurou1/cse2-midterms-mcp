const path = require('node:path');

module.exports = {
  apps: [{
    name: 'cse2-mcp',
    script: 'server.py',
    cwd: __dirname,
    interpreter: path.join(__dirname, '.venv', process.platform === 'win32' ? 'Scripts/pythonw.exe' : 'bin/python'),
    windowsHide: true,
    autorestart: true,
    restart_delay: 1500,
    max_restarts: 10,
    watch: false,
    out_file: path.join(__dirname, '.local/server-out.log'),
    error_file: path.join(__dirname, '.local/server-error.log'),
    time: true
  }, {
    name: 'cse2-tunnel',
    script: path.join(__dirname, '.local/bin/cloudflared.exe'),
    interpreter: 'none',
    windowsHide: true,
    args: ['tunnel', '--no-autoupdate', '--url', 'http://127.0.0.1:8765', '--http-host-header', '127.0.0.1:8765'],
    cwd: __dirname,
    autorestart: true,
    restart_delay: 2000,
    max_restarts: 5,
    out_file: path.join(__dirname, '.local/tunnel-out.log'),
    error_file: path.join(__dirname, '.local/tunnel-error.log'),
    time: true
  }]
};
