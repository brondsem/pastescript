# (c) 2005 Ian Bicking and contributors; written for Paste (http://pythonpaste.org)
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php
from paste.script.serve import ensure_port_cleanup
from paste.translogger import TransLogger

def run_server(wsgi_app, global_conf, host='localhost',
               port=8080):
    import wsgiserver

    logged_app = TransLogger(wsgi_app)
    port = int(port)
    # For some reason this is problematic on this server:
    ensure_port_cleanup([(host, port)], maxtries=2, sleeptime=0.5)
    server = wsgiserver.WSGIServer(logged_app, host=host, port=port)
    logged_app.logger.info('Starting HTTP server on http://%s:%s',
                           host, port)
    server.start()

