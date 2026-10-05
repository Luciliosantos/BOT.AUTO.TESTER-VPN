CRLF='\r\n'

def render_payload(value: str, host: str, port: int) -> bytes:
    if not value:
        return b''
    s = str(value)
    replacements = {
        '[host]': host, '[HOST]': host,
        '[app_host]': host, '[APP_HOST]': host,
        '[port]': str(port), '[PORT]': str(port),
        '[crlf]': CRLF, '[CRLF]': CRLF,
        '[crlf2]': CRLF + CRLF, '[CRLF2]': CRLF + CRLF,
        '\\r\\n': CRLF,
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    return s.encode('utf-8', errors='ignore')
