import json
import os
from email import policy
from email.parser import BytesParser
from pathlib import Path
from threading import Event

from aiosmtpd.controller import Controller


class TestMailbox:
    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        if not address.lower().endswith('.test'):
            return '550 Test recipients only'
        envelope.rcpt_tos.append(address)
        return '250 OK'

    async def handle_DATA(self, server, session, envelope):
        message=BytesParser(policy=policy.default).parsebytes(envelope.content)
        body=message.get_body(preferencelist=('plain',))
        row={'recipients':envelope.rcpt_tos,'subject':str(message['Subject']),
            'text':body.get_content() if body else ''}
        with Path(os.environ['TF_TEST_MAIL_FILE']).open('a',encoding='utf-8') as output:
            output.write(json.dumps(row,ensure_ascii=False)+'\n')
        return '250 Test message stored locally'


if __name__=='__main__':
    mailbox=Path(os.environ['TF_TEST_MAIL_FILE'])
    mailbox.parent.mkdir(parents=True,exist_ok=True)
    mailbox.write_text('',encoding='utf-8')
    controller=Controller(TestMailbox(),hostname='127.0.0.1',port=8025,data_size_limit=1024*1024)
    controller.start()
    try:Event().wait()
    finally:controller.stop()
