from __future__ import annotations

import logging
import asyncio
import urllib.parse
import sys
import typing
import re
import websockets
import Utils
import json

if __name__ == "__main__":
    Utils.init_logging("TextClient", exception_logger="Client")

from CommonClient import ClientCommandProcessor, CommonContext, get_base_parser, server_loop, gui_enabled
from MultiServer import CommandProcessor, mark_raw
from NetUtils import NetworkItem, NetworkSlot
from Utils import stream_input, async_start
from worlds.LauncherComponents import Component


if typing.TYPE_CHECKING:
    import kvui

logger = logging.getLogger("Client")

# without terminal, we have to use gui mode
gui_enabled = not sys.stdout or "--nogui" not in sys.argv


@Utils.cache_argsless
def get_ssl_context():
    import certifi
    return ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=certifi.where())


class DebugCommandProcessor(ClientCommandProcessor):
    def __init__(self, ctx: CommonContext):
        super().__init__(ctx)



class DebugContext(CommonContext):        
    # Text Mode to use !hint and such with games that have no text entry
    tags = CommonContext.tags | {"TextOnly"}
    game = ""  # empty matches any game since 0.3.2
    items_handling = 0b111  # receive all items for /received
    want_slot_data = False  # Can't use game specific slot_data
    command_processor = DebugCommandProcessor

    def __init__(self, server_address: typing.Optional[str], password: typing.Optional[str]) -> None:
        super().__init__(server_address, password)

    async def server_auth(self, password_requested: bool = False):
        if password_requested and not self.password:
            await super(DebugContext, self).server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    async def disconnect(self, allow_autoreconnect: bool = False):
        self.game = ""
        await super().disconnect(allow_autoreconnect)

    def on_package(self, cmd: str, args: dict):
        """For custom package handling in subclasses
        This gets called every time the server sends the client a message"""
        logger.info(args)
        if cmd == "Connected":
            self.game = self.slot_info[self.slot].game
        # I'm attempting to get the keys arg below because it will be false if the key doesn't exist
        if (cmd == "Retrieved" or cmd == "SetReply") and args.get("keys"): 
            
            # If the hint is for us, update the ui
            if self.ui and f"_read_hints_{self.team}_{self.slot}" in args["keys"]:
                self.ui.update_hints()

            # Get all keys returned
            for arg in args["keys"].keys():
                # Is it a hint?
                if arg.startswith("_read_hints_"):
                    # For each hint
                    for hint in args["keys"][arg]:
                        # Format the found/not found messages
                        if hint["found"]:
                            found_text = {"text": "(found)", "type": "color", "color": "green"}
                        else:
                            found_text = {"text": "(not found)", "type": "color", "color": "red"}
                        # I am manually reassembling the PrintJSON packet
                        output = {"cmd": "PrintJSON", 
                            "data": [
                            {"text": "[Hint]: "}, 
                            {"text": hint['receiving_player'], "type": "player_id"}, 
                            {"text": "'s "}, 
                            {"text": hint['item'], "player": hint['receiving_player'], "flags": hint['item_flags'], "type": "item_id"}, 
                            {"text": " is at "}, 
                            {"text": hint['location'], "player": hint['finding_player'], "type": "location_id"}, 
                            {"text": " in "}, 
                            {"text": hint['finding_player'], "type": "player_id"}, 
                            {"text": "'s World"}, {"text": ". "}, 
                            found_text
                            ], 
                            "type": "Hint", 
                            "receiving": hint['receiving_player'], 
                            "item": NetworkItem(item=hint['item'], location=hint['location'], player=hint['finding_player'], flags=1), 
                            "found": False}

                        # Then I tell the client to output it
                        # on_print_json never touches the server, it's for the local client to display
                        self.on_print_json(output)

    async def send_msgs(self, msgs: typing.List[typing.Any]) -> None:
        """ `msgs` JSON serializable """
        # Print sent messages for debugging
        logger.info(msgs)
        # Then tell the parent class to handle it
        await super().send_msgs(msgs)


def launch():
    # So you can run it without a GUI in your terminal
    async def main(args):
        ctx = DebugContext(args.connect, args.password)
        ctx.auth = args.name
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")

        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()

        await ctx.exit_event.wait()
        await ctx.shutdown()

    import colorama


    parser = get_base_parser(description="Gameless Archipelago Client, for text interfacing.")
    parser.add_argument("--name", default=None, help="Slot Name to connect as.")
    parser.add_argument("--url", nargs="?", help="Archipelago connection url")
    args = parser.parse_args()

    if args.url:
        if re.match(r"\d{5}", args.url): # Detects if only a port is entered
            raw_url = f"wss://archipelago.gg:{args.url}"
        else:
            raw_url = args.url
        url = urllib.parse.urlparse(raw_url)
        args.connect = url.netloc
        if url.username:
            args.name = urllib.parse.unquote(url.username)
        if url.password:
            args.password = urllib.parse.unquote(url.password)

    colorama.init()

    asyncio.run(main(args))
    colorama.deinit()


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)  # force log-level to work around log level resetting to WARNING
    launch()