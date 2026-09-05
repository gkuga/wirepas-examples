# wirepas-examples

Small, self-contained experiments for getting familiar with
[Wirepas Mesh](https://wirepas.com/) and its gateway stack.
Each directory is a uv project.

## Examples

| Name | Description |
|---|---|
| [hello](hello/) | Hello World: a backend app and a fake gateway exchanging Gateway-to-Backend API v2 messages over MQTT — no hardware required |

## How to run

This repo uses [uv](https://docs.astral.sh/uv/). Enter an example directory and
follow its README.

```bash
cd hello
uv sync
```
