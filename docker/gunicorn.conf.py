# Uma única instância, com concorrência pequena para o SQLite local.
bind = '0.0.0.0:8000'
workers = 1
worker_class = 'gthread'
threads = 2
timeout = 120
graceful_timeout = 30
worker_tmp_dir = '/tmp'
accesslog = '-'
errorlog = '-'
capture_output = True
max_requests = 1000
max_requests_jitter = 50
