# gunicorn runs the app in pre-forked worker processes. create_app() - and with it the OpenTelemetry SDK
# (exporters, background threads) - runs *inside* each worker, after the fork. Do not enable `preload_app`:
# the exporter threads would not survive the fork.
bind = "0.0.0.0:8000"
workers = 2
threads = 4
accesslog = "-"
