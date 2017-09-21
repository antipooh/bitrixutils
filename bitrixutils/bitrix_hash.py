import hashlib
import random
import string
import sys


def random_string(n):
    SYMBOLS = string.ascii_letters + string.digits
    return ''.join(random.choice(SYMBOLS) for _ in range(n))


def password_hash(password):
    salt = random_string(8)
    hash = hashlib.md5(f"{salt}{password}".encode())
    return f'{salt}{hash.hexdigest()}'


def main(argv=sys.argv):
    if len(sys.argv) != 2:
        print(f'Usage: {sys.argv[0]} <password>')
    print(password_hash(sys.argv[1]))


if __name__ == '__main__':
    main()
