"""
WSGI Entry Point untuk Production Deployment dengan Subpath /kolproject
========================================================================
"""

from app import app as flask_app

# Middleware untuk menambahkan prefix /kolproject ke semua URL
class ReverseProxied:
    def __init__(self, app, script_name='/kolproject'):
        self.app = app
        self.script_name = script_name

    def __call__(self, environ, start_response):
        script_name = self.script_name
        path_info = environ.get('PATH_INFO', '')
        
        # Jika request datang dari proxy dengan path /kolproject, strip prefix-nya dari PATH_INFO
        if path_info.startswith(script_name):
            environ['PATH_INFO'] = path_info[len(script_name):]
            
        # Set SCRIPT_NAME agar Flask generate URL yang benar
        environ['SCRIPT_NAME'] = script_name
        
        return self.app(environ, start_response)

# Apply middleware
flask_app.wsgi_app = ReverseProxied(flask_app.wsgi_app, script_name='/kol_scout')

# Expose app untuk gunicorn
app = flask_app

if __name__ == "__main__":
    flask_app.run()
