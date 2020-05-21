"""
This file is part of nucypher.

nucypher is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

nucypher is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with nucypher.  If not, see <https://www.gnu.org/licenses/>.

"""


import click
import os
from constant_sorrow.constants import NO_PASSWORD
from nacl.exceptions import CryptoError

from nucypher.blockchain.eth.decorators import validate_checksum_address
from nucypher.cli.literature import (
    COLLECT_ETH_PASSWORD,
    COLLECT_NUCYPHER_PASSWORD,
    DECRYPTING_CHARACTER_KEYRING,
    GENERIC_PASSWORD_PROMPT
)
from nucypher.config.constants import NUCYPHER_ENVVAR_KEYRING_PASSWORD
from nucypher.config.node import CharacterConfiguration


def get_password_from_prompt(prompt: str = GENERIC_PASSWORD_PROMPT, envvar: str = '', confirm: bool = False) -> str:
    password = os.environ.get(envvar, NO_PASSWORD)
    if password is NO_PASSWORD:  # Collect password, prefer env var
        password = click.prompt(prompt, confirmation_prompt=confirm, hide_input=True)
    return password


@validate_checksum_address
def get_client_password(checksum_address: str, envvar: str = '') -> str:
    client_password = get_password_from_prompt(prompt=COLLECT_ETH_PASSWORD.format(checksum_address=checksum_address),
                                               envvar=envvar,
                                               confirm=False)
    return client_password


def get_nucypher_password(confirm: bool = False, envvar=NUCYPHER_ENVVAR_KEYRING_PASSWORD) -> str:
    prompt = COLLECT_NUCYPHER_PASSWORD
    if confirm:
        from nucypher.config.keyring import NucypherKeyring
        prompt += f" ({NucypherKeyring.MINIMUM_PASSWORD_LENGTH} character minimum)"
    keyring_password = get_password_from_prompt(prompt=prompt, confirm=confirm, envvar=envvar)
    return keyring_password


def unlock_nucypher_keyring(emitter, password: str, character_configuration: CharacterConfiguration) -> bool:
    emitter.message(DECRYPTING_CHARACTER_KEYRING.format(name=character_configuration.NAME), color='yellow')

    # precondition
    if character_configuration.dev_mode:
        return True  # Dev accounts are always unlocked

    # unlock
    try:
        character_configuration.attach_keyring()
        character_configuration.keyring.unlock(password=password)  # Takes ~3 seconds, ~1GB Ram
    except CryptoError:
        raise character_configuration.keyring.AuthenticationFailed
    else:
        return True