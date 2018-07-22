# https://ffmpeg.org/ffplay.html
import shlex
import subprocess
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Type, List

from dataclasses import dataclass

if TYPE_CHECKING:
    import numpy as np
    from ovgenpy.ovgenpy import Config


RGB_DEPTH = 3


class OutputConfig:
    cls: 'Type[Output]'

    def __call__(self, ovgen_cfg: 'Config'):
        return self.cls(ovgen_cfg, cfg=self)


class Output(ABC):
    def __init__(self, ovgen_cfg: 'Config', cfg: OutputConfig):
        self.ovgen_cfg = ovgen_cfg
        self.cfg = cfg

    @abstractmethod
    def write_frame(self, frame: 'np.ndarray') -> None:
        """ Output a Numpy ndarray. """


# Glue logic

def register_output(config_t: Type[OutputConfig]):
    def inner(output_t: Type[Output]):
        config_t.cls = output_t
        return output_t

    return inner


FFMPEG = 'ffmpeg'
FFPLAY = 'ffplay'


assert RGB_DEPTH == 3
def ffmpeg_input_video(cfg: 'Config') -> List[str]:
    fps = cfg.fps
    width = cfg.render.width
    height = cfg.render.height

    return [f'-f rawvideo -pixel_format rgb24 -video_size {width}x{height}',
            f'-framerate {fps}',
            '-i -']


def ffmpeg_input_audio(audio_path: str) -> List[str]:
    return ['-i', audio_path]


FFMPEG_OUTPUT_VIDEO_DEFAULT = '-c:v libx264 -crf 18 -bf 2 -flags +cgop -pix_fmt yuv420p -movflags faststart'
FFMPEG_OUTPUT_AUDIO_DEFAULT = '-c:a aac -b:a 384k'


class _FFmpegCommand:
    def __init__(self, templates: List[str], ovgen_cfg: 'Config'):
        self.templates = templates
        self.ovgen_cfg = ovgen_cfg

        self.templates += ffmpeg_input_video(ovgen_cfg)  # video
        if self.ovgen_cfg.audio_path:
            self.templates += ffmpeg_input_audio(audio_path=ovgen_cfg.audio_path)    # audio

    def add_output(self, cfg: 'FFmpegOutputConfig') -> None:
        self.templates.append(cfg.video_template)  # video
        if self.ovgen_cfg.audio_path:
            self.templates.append(cfg.audio_template)  # audio

    def popen(self) -> subprocess.Popen:
        return subprocess.Popen(self._generate_args(), stdin=subprocess.PIPE)

    def _generate_args(self) -> List[str]:
        return [arg
                for template in self.templates
                for arg in shlex.split(template)]


class ProcessOutput(Output):
    def open(self, popen: subprocess.Popen):
        self._popen = popen
        self._stream = self._popen.stdin
        # Python documentation discourages accessing popen.stdin. It's wrong.
        # https://stackoverflow.com/a/9886747

    def write_frame(self, frame: bytes) -> None:
        self._stream.write(frame)

    def close(self):
        self._stream.close()
        self._popen.wait()


# FFmpegOutput
@dataclass
class FFmpegOutputConfig(OutputConfig):
    path: str
    video_template: str = FFMPEG_OUTPUT_VIDEO_DEFAULT
    audio_template: str = FFMPEG_OUTPUT_AUDIO_DEFAULT


@register_output(FFmpegOutputConfig)
class FFmpegOutput(ProcessOutput):
    def __init__(self, ovgen_cfg: 'Config', cfg: FFmpegOutputConfig):
        super().__init__(ovgen_cfg, cfg)

        ffmpeg = _FFmpegCommand([FFMPEG, '-y'], ovgen_cfg)
        ffmpeg.add_output(cfg)
        self.open(ffmpeg.popen())


# FFplayOutput
class FFplayOutputConfig(OutputConfig):
    pass


@register_output(FFplayOutputConfig)
class FFplayOutput(ProcessOutput):
    def __init__(self, ovgen_cfg: 'Config', cfg: FFplayOutputConfig):
        super().__init__(ovgen_cfg, cfg)

        ffplay = _FFmpegCommand([FFPLAY], ovgen_cfg)
        self.open(ffplay.popen())


# ImageOutput
@dataclass
class ImageOutputConfig:
    path_prefix: str


@register_output(ImageOutputConfig)
class ImageOutput(Output):
    pass
