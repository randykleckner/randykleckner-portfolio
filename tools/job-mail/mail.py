#!/usr/bin/env python3
"""Read a private R2 inbox and explicitly send a prepared email through Cloudflare."""
import argparse
import email
from email import policy
import html
import json
import os
from pathlib import Path
import re
import sys
import urllib.request
import urllib.error

CONFIG = Path.home() / '.config' / 'job-mail' / 'config.json'
ADDRESS = 'randy@randykleckner.com'
MAX_BYTES = 25 * 1024 * 1024

def config():
    if not CONFIG.exists():
        raise ValueError(f'Credentials are not configured: {CONFIG}')
    if CONFIG.stat().st_mode & 0o077:
        raise ValueError('Credential file must be private: chmod 600 ' + str(CONFIG))
    return json.loads(CONFIG.read_text())

def draft_payload(path):
    draft = json.loads(Path(path).read_text())
    recipient = draft.get('to', '')
    if not isinstance(recipient, str) or not re.fullmatch(r'[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+', recipient):
        raise ValueError('Provide exactly one recipient email address.')
    subject, body = draft.get('subject'), draft.get('text')
    if not isinstance(subject, str) or not subject.strip() or '\n' in subject or '\r' in subject:
        raise ValueError('A single-line subject is required.')
    if not isinstance(body, str) or not body.strip():
        raise ValueError('Plain-text message body is required.')
    payload = {'from': ADDRESS, 'to': recipient, 'subject': subject, 'text': body,
               'html': '<p>' + html.escape(body).replace('\n', '<br>') + '</p>'}
    if len(json.dumps(payload).encode()) > 4 * 1024 * 1024:
        raise ValueError('Draft is too large.')
    return payload

def send(args):
    payload = draft_payload(args.draft)
    if not args.confirm_send:
        print(json.dumps({'status': 'preview_only', 'message': payload}, indent=2))
        return
    cfg = config()
    account = cfg['account_id']
    if not re.fullmatch(r'[a-f0-9]{32}', account):
        raise ValueError('Invalid Cloudflare account ID.')
    req = urllib.request.Request(
        f'https://api.cloudflare.com/client/v4/accounts/{account}/email/sending/send',
        data=json.dumps(payload).encode(), method='POST',
        headers={'Authorization': 'Bearer ' + cfg['email_send_token'], 'Content-Type': 'application/json'})
    # No automatic resend: a timeout may follow a successful send.
    with urllib.request.urlopen(req, timeout=45) as response:
        result = json.load(response)
    if not result.get('success'):
        raise ValueError('Cloudflare did not confirm acceptance. Inspect the sending activity log before retrying.')
    print(json.dumps(result.get('result', {}), indent=2))

def sync(args):
    import boto3
    cfg = config()
    account = cfg['account_id']
    if not re.fullmatch(r'[a-f0-9]{32}', account):
        raise ValueError('Invalid Cloudflare account ID.')
    s3 = boto3.client('s3', endpoint_url=f'https://{account}.r2.cloudflarestorage.com', region_name='auto',
                      aws_access_key_id=cfg['r2_access_key_id'], aws_secret_access_key=cfg['r2_secret_access_key'])
    dest = Path(args.output).expanduser()
    dest.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(dest, 0o700)
    count = 0
    for page in s3.get_paginator('list_objects_v2').paginate(Bucket='randy-job-mail', Prefix='inbox/'):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if not re.fullmatch(r'inbox/[a-f0-9]{64}\.eml', key) or obj['Size'] > MAX_BYTES:
                continue
            path = dest / key.split('/')[1]
            if path.exists():
                continue
            response = s3.get_object(Bucket='randy-job-mail', Key=key)
            stream = response['Body']
            try:
                raw = stream.read(MAX_BYTES + 1)
            finally:
                stream.close()
            if len(raw) > MAX_BYTES:
                raise ValueError('Incoming email exceeds limit.')
            with path.open('xb') as out:
                os.chmod(path, 0o600)
                out.write(raw)
            count += 1
    print(json.dumps({'downloaded': count, 'directory': str(dest)}))

def read(args):
    path = Path(args.file)
    with path.open('rb') as source:
        raw = source.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('Incoming email exceeds limit.')
    msg = email.message_from_bytes(raw, policy=policy.default)
    body = msg.get_body(preferencelist=('plain',))
    print(json.dumps({'untrusted_email': True, 'from': str(msg.get('From', '')),
        'to': str(msg.get('To', '')), 'subject': str(msg.get('Subject', '')),
        'date': str(msg.get('Date', '')), 'message_id': str(msg.get('Message-ID', '')),
        'text': body.get_content() if body else '[No plain-text body; inspect manually]',
        'attachments': [part.get_filename() for part in msg.iter_attachments()]}, indent=2))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    cmd = subs.add_parser('sync'); cmd.add_argument('--output', default='~/.local/share/job-mail/inbox'); cmd.set_defaults(func=sync)
    cmd = subs.add_parser('read'); cmd.add_argument('file'); cmd.set_defaults(func=read)
    cmd = subs.add_parser('send'); cmd.add_argument('draft'); cmd.add_argument('--confirm-send', action='store_true'); cmd.set_defaults(func=send)
    args = parser.parse_args()
    try:
        args.func(args)
    except urllib.error.HTTPError as exc:
        print(f'Cloudflare HTTP {exc.code}; no automatic retry was attempted.', file=sys.stderr); sys.exit(1)
    except (ValueError, KeyError, OSError, ImportError) as exc:
        print(str(exc), file=sys.stderr); sys.exit(1)

if __name__ == '__main__':
    main()
