from .digest import nhi_digest


def register_cli_commands(app):
    app.cli.add_command(nhi_digest)
