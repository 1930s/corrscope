from os.path import abspath
from typing import TYPE_CHECKING, Optional, Union

import attr
from ruamel.yaml.comments import CommentedMap

from corrscope.config import register_config, Alias, CorrError
from corrscope.triggers import ITriggerConfig
from corrscope.util import coalesce
from corrscope.wave import _WaveConfig, Wave

if TYPE_CHECKING:
    from corrscope.corrscope import Config


@register_config
class ChannelConfig:
    wav_path: str

    # Supplying a dict inherits attributes from global trigger.
    trigger: Union[ITriggerConfig, dict, None] = attr.Factory(dict)    # TODO test channel-specific triggers
    # Multiplies how wide the window is, in milliseconds.
    trigger_width: Optional[int] = None
    render_width: Optional[int] = None

    ampl_ratio: float = 1.0     # TODO use amplification = None instead?
    line_color: Optional[str] = None

    # region Legacy Fields
    trigger_width_ratio = Alias('trigger_width')
    render_width_ratio = Alias('render_width')
    # endregion


class Channel:
    # trigger_samp is unneeded, since __init__ (not CorrScope) constructs triggers.
    render_samp: int
    # TODO add a "get_around" method for rendering (also helps test_channel_subsampling)
    # Currently CorrScope peeks at Channel.render_samp and render_stride (bad).

    # Product of corr_cfg.trigger/render_subsampling and trigger/render_width.
    trigger_stride: int
    render_stride: int

    def __init__(self, cfg: ChannelConfig, corr_cfg: 'Config'):
        self.cfg = cfg

        # Create a Wave object.
        wcfg = _WaveConfig()
        wcfg.amplification = corr_cfg.amplification * cfg.ampl_ratio
        self.wave = Wave(wcfg, abspath(cfg.wav_path))

        # `subsampling` increases `stride` and decreases `nsamp`.
        # `width` increases `stride` without changing `nsamp`.
        tsub = corr_cfg.trigger_subsampling
        tw = coalesce(cfg.trigger_width, corr_cfg.trigger_width)

        rsub = corr_cfg.render_subsampling
        rw = coalesce(cfg.render_width, corr_cfg.render_width)

        # nsamp = orig / subsampling
        # stride = subsampling * width
        def calculate_nsamp(width_ms, sub):
            width_s = width_ms / 1000
            return round(width_s * self.wave.smp_s / sub)

        trigger_samp = calculate_nsamp(corr_cfg.trigger_ms, tsub)
        self.render_samp = calculate_nsamp(corr_cfg.render_ms, rsub)

        self.trigger_stride = tsub * tw
        self.render_stride = rsub * rw

        # Create a Trigger object.
        if isinstance(cfg.trigger, ITriggerConfig):
            tcfg = cfg.trigger
        elif isinstance(cfg.trigger, (CommentedMap, dict)):  # CommentedMap may/not be subclass of dict.
            tcfg = attr.evolve(corr_cfg.trigger, **cfg.trigger)
        elif cfg.trigger is None:
            tcfg = corr_cfg.trigger
        else:
            raise CorrError(
                f'invalid per-channel trigger {cfg.trigger}, type={type(cfg.trigger)}, '
                f'must be (*)TriggerConfig, dict, or None')

        self.trigger = tcfg(
            wave=self.wave,
            tsamp=trigger_samp,
            stride=self.trigger_stride,
            fps=corr_cfg.fps
        )

