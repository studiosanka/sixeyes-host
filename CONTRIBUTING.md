# Contributing

This repository is maintained by Studio Sanka members. We are not accepting pull requests or outside contributions at this time.

Found a bug, or have a question or idea? Please open an issue: https://github.com/studiosanka/sixeyes-host/issues. We read everything, though we cannot promise a reply to every message.

Licence: Apache-2.0 (see `LICENSE`). Documentation text is shared under the same terms in this repository.

## For maintainers

- Change the protocol only in `protocol/messages.yaml`, then run `python protocol/generate.py`. Never edit `protocol/generated/` or `python/src/sixeyes_host/_protocol.py` by hand.
- Run the tests: `PYTHONPATH=python/src python -m unittest discover -s python/tests` and `node --test protocol/ts/codec.test.ts`.
- Keep the README to one screen and put technical detail in `docs/appendix/`.
