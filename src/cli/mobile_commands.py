"""
Conversational command grammar for workout logging.

One unified interface for desktop and phone terminals.
"""

import re
from typing import Dict, Optional, Tuple


COMMAND_HELP = """
Commands:
  help                      Show this help
  /help                     Show this help
  status                    Show current session + draft exercise state
  ex <exercise name>        Start a new draft exercise
  next <exercise name>      Alias for ex <exercise name>
  w <weight>x<reps>[@rpe]   Add warmup set (example: w 40x5)
  s <weight>x<reps>[@rpe]   Add working set (example: s 80x5@8)
  note <text>               Add/update note on current draft exercise
  goal <text>               Set/update exercise goal (e.g. 60kg x 3 sets x 8-10)
  rest <minutes>            Set rest minutes for current draft exercise
  tempo <text>              Set tempo (e.g. 3-1-1-0)
  muscles <csv>             Set target muscles
  cue <text>                Add one cue line
  warmup_note <text>        Add/update warmup note
  undo                      Remove last set from current draft (working first)
  done                      Commit current draft exercise into session
  finish                    Finalize session and save
  cancel                    Cancel session without saving
  restart                   Discard current session and start fresh setup

Quick exits:
  quit / exit / stop        Same as cancel

Natural language also works, for example:
  "let's do incline dumbbell press"
  "next exercise lat pulldown"
  "warmup 20x8"
  "did 80 for 5 at 8"
The app will confirm what it understood before applying (LLM mode).

Safety:
  - `finish` and `cancel` are explicit commands.
  - The app will not auto-finish or auto-cancel from ambiguous text.
"""


def parse_command(line: str) -> Tuple[str, str]:
    """Parse user command into (command, argument)."""
    raw = (line or "").strip()
    if not raw:
        return "", ""

    if " " in raw:
        command, arg = raw.split(" ", 1)
        return command.lower().strip(), arg.strip()
    return raw.lower(), ""


def normalize_command(command: str) -> str:
    """Normalize aliases to canonical command names."""
    aliases = {
        "h": "help",
        "?": "help",
        "/help": "help",
        "/status": "status",
        "/restart": "restart",
        "/quit": "cancel",
        "/exit": "cancel",
        "/stop": "cancel",
        "st": "status",
        "wnote": "warmup_note",
        "warmupnote": "warmup_note",
        "warmup-notes": "warmup_note",
        "warmup_notes": "warmup_note",
        "cues": "cue",
    }
    return aliases.get(command, command)


def parse_set_notation(raw: str) -> Optional[Dict[str, float]]:
    """
    Parse compact set notation: <weight>x<reps>[@rpe].

    Examples:
    - 80x5
    - 80x5@8
    - 82.5 x 6 @ 9
    """
    text = (raw or "").strip().lower().replace(" ", "")
    if not text:
        return None

    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)x([0-9]+)(?:@([0-9]+(?:\.[0-9]+)?))?", text)
    if not match:
        return None

    weight = float(match.group(1))
    reps = int(match.group(2))
    rpe_match = match.group(3)
    rpe = float(rpe_match) if rpe_match is not None else None

    set_data: Dict[str, float] = {
        "weight": weight,
        "reps": reps,
    }
    if rpe is not None:
        set_data["rpe"] = rpe
    return set_data
