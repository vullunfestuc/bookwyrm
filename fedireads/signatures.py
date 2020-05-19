import hashlib
from urllib.parse import urlparse
from base64 import b64encode, b64decode

from Crypto import Random
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15 #pylint: disable=no-name-in-module
from Crypto.Hash import SHA256


def create_key_pair():
    random_generator = Random.new().read
    key = RSA.generate(1024, random_generator)
    private_key = key.export_key().decode('utf8')
    public_key = key.publickey().export_key().decode('utf8')

    return private_key, public_key


def make_signature(sender, destination, date, digest):
    inbox_parts = urlparse(destination)
    signature_headers = [
        '(request-target): post %s' % inbox_parts.path,
        'host: %s' % inbox_parts.netloc,
        'date: %s' % date,
        'digest: %s' % digest,
    ]
    message_to_sign = '\n'.join(signature_headers)
    signer = pkcs1_15.new(RSA.import_key(sender.private_key))
    signed_message = signer.sign(SHA256.new(message_to_sign.encode('utf8')))
    signature = {
        'keyId': '%s#main-key' % sender.remote_id,
        'algorithm': 'rsa-sha256',
        'headers': '(request-target) host date digest',
        'signature': b64encode(signed_message).decode('utf8'),
    }
    return ','.join('%s="%s"' % (k, v) for (k, v) in signature.items())

def make_digest(data):
    return 'SHA-256=' + b64encode(hashlib.sha512(data).digest()).decode('utf-8')

def verify_digest(request):
    algorithm, digest = request.headers['digest'].split('=', 1)
    if algorithm == 'SHA-256':
        hash_function = hashlib.sha256
    elif algorithm == 'SHA-512':
        hash_function = hashlib.sha512
    else:
        raise ValueError("Unsupported hash function: {}".format(algorithm))

    expected = hash_function(request.body).digest()
    if b64decode(digest) != expected:
        return ValueError("Invalid HTTP Digest header")

class Signature:
    def __init__(self, key_id, headers, signature):
        self.key_id = key_id
        self.headers = headers
        self.signature = signature

    @classmethod
    def parse(cls, request):
        signature_dict = {}
        for pair in request.headers['Signature'].split(','):
            k, v = pair.split('=', 1)
            v = v.replace('"', '')
            signature_dict[k] = v

        try:
            key_id = signature_dict['keyId']
            headers = signature_dict['headers']
            signature = b64decode(signature_dict['signature'])
        except KeyError:
            raise ValueError('Invalid auth header')

        return cls(key_id, headers, signature)

    def verify(self, public_key, request):
        ''' verify rsa signature '''
        public_key = RSA.import_key(public_key)

        comparison_string = []
        for signed_header_name in self.headers.split(' '):
            if signed_header_name == '(request-target)':
                comparison_string.append(
                    '(request-target): post %s' % request.path)
            else:
                if signed_header_name == 'digest':
                    verify_digest(request)
                comparison_string.append('%s: %s' % (
                    signed_header_name,
                    request.headers[signed_header_name]
                ))
        comparison_string = '\n'.join(comparison_string)

        signer = pkcs1_15.new(public_key)
        digest = SHA256.new()
        digest.update(comparison_string.encode())

        # raises a ValueError if it fails
        signer.verify(digest, self.signature)
