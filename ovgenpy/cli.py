from pathlib import Path
from typing import Optional, List, Tuple

import click

from ovgenpy.channel import ChannelConfig
from ovgenpy.config import OvgenError, yaml
from ovgenpy.outputs import FFmpegOutputConfig, FFplayOutputConfig
from ovgenpy.ovgenpy import default_config, Config, Ovgen


Folder = click.Path(exists=True, file_okay=False)
File = click.Path(exists=True, dir_okay=False)


# https://github.com/pallets/click/issues/473
# @platformio requires some functionality which doesn't work in Click 6.
# Click 6 is marked as stable, but http://click.pocoo.org/ redirects to /5/.
# wat


# If multiple `--` names are supplied to @click.option, the last one will be used.
# possible_names = [('-', 'w'), ('--', 'write')]
# possible_names.sort(key=lambda x: len(x[0]))
# name = possible_names[-1][1].replace('-', '_').lower()


YAML_EXTS = ['.yaml']


@click.command()
# Inputs
@click.argument('files', nargs=-1)
# Override default .yaml settings (only if YAML file not supplied)
# Incorrect [option] name order: https://github.com/pallets/click/issues/793
@click.option('--audio', '-a', type=File)
@click.option('--video-output', '-o', type=click.Path(dir_okay=False))
# Disables GUI
@click.option('--write-cfg', '-w', nargs=1, type=click.Path(dir_okay=False))
@click.option('--play', '-p', is_flag=True)
def main(
        files: Tuple[str],
        # cfg
        audio: Optional[str],
        video_output: Optional[str],
        # gui
        write_cfg: Optional[str],
        play: bool,
):
    """
    GUI:
    ovgenpy
    ovgenpy file.yaml
    ovgenpy wildcard/wav/folder ... [--options]

    CLI:
    ovgenpy wildcard/wav/folder ... [--options] --write-cfg file.yaml [--play]
    ??? ovgenpy wildcard/wav/folder ... --play
    ovgenpy file.yaml --play
    ovgenpy file.yaml --write-yaml

    - You can specify as many wildcards or wav files as you want.
    - You can only supply one folder, with no files/wildcards.
    """

    show_gui = (not write_cfg and not play)

    # Create cfg: Config object.
    cfg: Config = None

    wav_prefix = Path()
    wav_list: List[Path] = []
    for name in files:
        path = Path(name)
        if path.is_dir():
            # Add a directory.
            if len(files) > 1:
                raise click.ClickException(
                    f'When supplying folder {path}, you cannot supply other files/folders')
            wav_prefix = path
            matches = sorted(path.glob('*.wav'))
            wav_list += matches
            break

        elif path.suffix in YAML_EXTS:
            # Load a YAML file to cfg, and skip default_config().
            if len(files) > 1:
                raise click.ClickException(
                    f'When supplying config {path}, you cannot supply other files/folders')
            cfg = yaml.load(path)
            break

        else:
            # Load one or more wav files.
            matches = sorted(Path().glob(name))
            if not matches:
                matches = [path]
                if not path.exists():
                    raise click.ClickException(
                        f'Supplied nonexistent file or wildcard {path}')
            wav_list += matches

    if not cfg:
        wav_prefix = str(wav_prefix)
        wav_list = [str(wav_path) for wav_path in wav_list]

        channels = [ChannelConfig(wav_path) for wav_path in wav_list]

        if video_output:
            outputs = [FFmpegOutputConfig(video_output)]
        else:
            outputs = [FFplayOutputConfig()]

        # TODO test cfg, ensure wav_prefix and wav_list are correct
        # maybe I should use a list comprehension to parse cfg.channels to List[str].

        cfg = default_config(
            master_audio=audio,
            # fps=default,
            wav_prefix=wav_prefix,
            channels=channels,
            # width_ms...trigger=default,
            # amplification...render=default,
            outputs=outputs
        )

    if show_gui:
        raise OvgenError('GUI not implemented')
    else:
        if write_cfg:
            # TODO test writing YAML file
            yaml.dump(cfg, Path(write_cfg))

        if play:
            Ovgen(cfg).play()