const path = require('node:path');

module.exports = {
  apps: [{
    name: 'cse2-mcp',
    script: 'server.py',
    cwd: __dirname,
    interpreter: path.join(__dirname, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python'),
    autorestart: true,
    restart_delay: 1500,
    max_restarts: 10,
    watch: false,
    out_file: path.join(__dirname, '.local/server-out.log'),
    error_file: path.join(__dirname, '.local/server-error.log'),
    time: true
  }]
};
