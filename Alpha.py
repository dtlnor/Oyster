from vapoursynth import *
from VaporMagik import *
import math

fmtc_args = dict(fulls=True, fulld=True)
msuper_args = dict(hpad=0, vpad=0, sharp=2, levels=0)
manalyze_args = dict(search=3, truemotion=False, trymany=True, levels=0, badrange=-24, divide=0, dct=0)
mrecalculate_args = dict(truemotion=False, search=3, smooth=1, divide=0, dct=0)
mdegrain_args = dict(thscd1=16320.0, thscd2=255.0)
nnedi_args = dict(field=1, dh=True, nns=4, qual=2, etype=1, nsize=0)
dfttest_args = dict(smode=0, sosize=0, tbsize=1, tosize=0, tmode=0)

def CosineInterpolate(Begin, End, Step):
    def CurveStepDomain(x):
        x *= 0.5 * math.pi / (Step + 1)
        return 1 - math.cos(x)
    return [Begin + CurveStepDomain(x) * (End - Begin) for x in range(Step + 2)]

def ConvexAttenuate(Value, Scale, Multiplier):
    """
    lim x * log(1 + 1 / x) as x->inf = 1
    lim x * log(1 + 1 / x) as x->0 = 0
    """
    ScaledValue = math.pow(Scale * Value, Multiplier)
    Coefficient = ScaledValue * math.log(1 + 1 / ScaledValue)
    return Coefficient * Value

def ConcaveAttenuate(Value, Alpha, Beta):
    """
    lim log(1 + x) / x as x->inf = 0
    lim log(1 + x) / x as x->0 = 1
    """
    ScaledValues = [Alpha * Value, Beta * Value]
    Coefficients = [math.log(1 + x) / x for x in ScaledValues]
    return (Coefficients[0] + Coefficients[1]) * Value / 2

def _init():
    RegisterPlugin(core.std)
    RegisterPlugin(core.fmtc)
    RegisterPlugin(core.nnedi3)
    RegisterPlugin(core.knlm)
    RegisterPlugin(core.dfttest)
    RegisterPlugin(core.mvsf, lambda _, FilterName: 'M' + FilterName)
    RegisterPlugin(core.bm3d, lambda _, FilterName: 'BM3D' + FilterName + 'Native')

@Inject
def Mirror(self: VideoNode, left, right, top, bottom):
    clip = self
    vertical_filler = clip.FlipVertical()
    if top > 0:
        top_filler = vertical_filler.Crop(0, 0, vertical_filler.height - top - 1, 1)
        clip = [top_filler, clip].StackVertical()
    if bottom > 0:
        bottom_filler = vertical_filler.Crop(0, 0, 1, vertical_filler.height - bottom - 1)
        clip = [clip, bottom_filler].StackVertical()
    horizontal_filler = clip.FlipHorizontal()
    if left > 0:
        left_filler = horizontal_filler.Crop(horizontal_filler.width - left - 1, 1, 0, 0)
        clip = [left_filler, clip].StackHorizontal()
    if right > 0:
        right_filler = horizontal_filler.Crop(1, horizontal_filler.width - right - 1, 0, 0)
        clip = [clip, right_filler].StackHorizontal()
    return clip

@Inject
def TemporalMirror(self: VideoNode, radius):
    if radius > 0:
        head = self[1: 1 + radius].Reverse()
        tail = self[self.num_frames - 1 - radius: self.num_frames - 1].Reverse()
        return head + self + tail
    else:
        return self

@Inject
def NLMeans(self: VideoNode, d, a, s, h, rclip = None):
    clip = self.Mirror(a + s, a + s, a + s, a + s).TemporalMirror(d)
    rclip = rclip.Mirror(a + s, a + s, a + s, a + s).TemporalMirror(d) if rclip is not None else None
    clip = clip.KNLMeansCL(d = d, a = a, s = s, h = h, channels = 'Y', wref = 1.0, rclip = rclip)
    clip = clip.Crop(a + s, a + s, a + s, a + s)
    return clip[d: clip.num_frames - d]

@Inject
def BM3DBasic(self: VideoNode, ref, **kw):
    block_size = kw['block_size']
    radius = kw['radius']
    clip = self.Mirror(block_size, block_size, block_size, block_size).TemporalMirror(radius)
    ref = ref.Mirror(block_size, block_size, block_size, block_size).TemporalMirror(radius) if ref is not None else None
    clip = clip.BM3DVBasicNative(ref, **kw).BM3DVAggregateNative(radius, 1)
    clip = clip.Crop(block_size, block_size, block_size, block_size)
    return clip[radius: clip.num_frames - radius]

@Inject
def BM3DFinal(self: VideoNode, ref, wref, **kw):
    block_size = kw['block_size']
    radius = kw['radius']
    clip = self.Mirror(block_size, block_size, block_size, block_size).TemporalMirror(radius)
    ref = ref.Mirror(block_size, block_size, block_size, block_size).TemporalMirror(radius)
    wref = wref.Mirror(block_size, block_size, block_size, block_size).TemporalMirror(radius) if wref is not None else None
    clip = clip.BM3DVFinalNative(ref, wref, **kw).BM3DVAggregateNative(radius, 1)
    clip = clip.Crop(block_size, block_size, block_size, block_size)
    return clip[radius: clip.num_frames - radius]

@Inject
def DrawMacroblockMask(self: VideoNode, left = 0, right = 0, top = 0, bottom = 0):
    ref_width = self.width + left + right
    ref_height = self.height + top + bottom
    clip = self.BlankClip(24, 24, color = 0.0)
    clip = clip.AddBorders(4, 4, 4, 4, color = 1.0)
    clip = [clip, clip, clip, clip].StackHorizontal()
    clip = [clip, clip, clip, clip].StackVertical()
    clip = clip.resample(32, 32, kernel="point", **fmtc_args)
    clip = clip.Expr("x 0 > 1 0 ?")
    h_extend = [clip] * (ref_width // 32 + 1)
    clip = h_extend.StackHorizontal()
    v_extend = [clip] * (ref_height // 32 + 1)
    clip = v_extend.StackVertical()
    clip = clip.CropAbs(ref_width, ref_height, 0, 0)
    return clip.Crop(left, right, top, bottom)

@Inject
def ReplaceHighFrequencyComponent(self: VideoNode, ref, sbsize, slocation):
    clip = self.Mirror(sbsize, sbsize, sbsize, sbsize)
    ref = ref.Mirror(sbsize, sbsize, sbsize, sbsize)
    low_freq = clip.DFTTest(sbsize = sbsize, slocation = slocation, **dfttest_args)
    high_freq = ref.MakeDiff(ref.DFTTest(sbsize = sbsize, slocation = slocation, **dfttest_args))
    clip = low_freq.MergeDiff(high_freq)
    return clip.Crop(sbsize, sbsize, sbsize, sbsize)

def _super(clip, pel):
    clip = clip.Mirror(64, 64, 64, 64)
    clip = clip.nnedi3(**nnedi_args).Transpose().nnedi3(**nnedi_args).Transpose()
    if pel == 4:
        clip = clip.nnedi3(**nnedi_args).Transpose().nnedi3(**nnedi_args).Transpose()
    return clip

def _basic(clip, superclip, radius, pel, sad, me_sad_upperbound, me_sad_lowerbound):
    clip = clip.Mirror(64, 64, 64, 64).TemporalMirror(radius)
    superclip = superclip.TemporalMirror(radius) if superclip is not None else None
    me_sad = CosineInterpolate(me_sad_lowerbound, me_sad_upperbound, 3)
    me_super = clip.MSuper(pelclip=superclip, rfilter=4, pel=pel, **msuper_args)
    degrain_super = clip.MSuper(pelclip=superclip, rfilter=2, pel=pel, **msuper_args)
    vec = me_super.MAnalyze(radius=radius, overlap=32, blksize=64, searchparam=4, **manalyze_args)
    vec = me_super.MRecalculate(vec, overlap=16, blksize=32, searchparam=8, thsad=me_sad[0], **mrecalculate_args)
    vec = me_super.MRecalculate(vec, overlap=8, blksize=16, searchparam=16, thsad=me_sad[1], **mrecalculate_args)
    vec = me_super.MRecalculate(vec, overlap=4, blksize=8, searchparam=32, thsad=me_sad[2], **mrecalculate_args)
    vec = me_super.MRecalculate(vec, overlap=2, blksize=4, searchparam=64, thsad=me_sad[3], **mrecalculate_args)
    vec = me_super.MRecalculate(vec, overlap=1, blksize=2, searchparam=128, thsad=me_sad[4], **mrecalculate_args)
    clip = clip.MDegrain(degrain_super, vec, thsad=sad, **mdegrain_args)
    clip = clip.Crop(64, 64, 64, 64)
    return clip[radius: clip.num_frames - radius]

def Super(clip, pel = 4):
    if not isinstance(clip, VideoNode):
       raise TypeError("Oyster.Super: clip has to be a video clip!")
    elif clip.format.sample_type != FLOAT or clip.format.bits_per_sample < 32:
       raise TypeError("Oyster.Super: clip has to be of fp32 sample type!")  
    elif clip.format.color_family != GRAY:
       raise RuntimeError("Oyster.Super: clip has to be of GRAY format!")
    if not isinstance(pel, int):
       raise TypeError("Oyster.Super: pel has to be an integer!")
    elif pel != 2 and pel != 4:
       raise RuntimeError("Oyster.Super: pel has to be 2 or 4!")
    _init()
    return _super(clip.SetFieldBased(0), pel)

def Basic(clip, superclip = None, radius = 6, pel = 4, sad = 2000.0, me_sad_upperbound = None, me_sad_lowerbound = None):
    if not isinstance(clip, VideoNode):
       raise TypeError("Oyster.Basic: clip has to be a video clip!")
    elif clip.format.sample_type != FLOAT or clip.format.bits_per_sample < 32:
       raise TypeError("Oyster.Basic: clip has to be of fp32 sample type!")  
    elif clip.format.color_family != GRAY:
       raise RuntimeError("Oyster.Basic: clip has to be of GRAY format!")
    if not isinstance(superclip, VideoNode) and superclip is not None:
       raise TypeError("Oyster.Basic: superclip has to be a video clip or None!")
    if not isinstance(radius, int):
       raise TypeError("Oyster.Basic: radius has to be an integer!")
    elif radius < 1:
       raise RuntimeError("Oyster.Basic: radius has to be greater than 0!")
    if not isinstance(pel, int):
       raise TypeError("Oyster.Basic: pel has to be an integer!")
    elif pel != 1 and pel != 2 and pel != 4:
       raise RuntimeError("Oyster.Basic: pel has to be 1, 2 or 4!")
    if not isinstance(sad, float) and not isinstance(sad, int):
       raise TypeError("Oyster.Basic: sad has to be a real number!")
    elif sad <= 0.0:
       raise RuntimeError("Oyster.Basic: sad has to be greater than 0!")
    if not isinstance(me_sad_upperbound, float) and not isinstance(me_sad_upperbound, int) and me_sad_upperbound is not None:
       raise TypeError("Oyster.Basic: me_sad_upperbound has to be a real number or None!")
    if not isinstance(me_sad_lowerbound, float) and not isinstance(me_sad_lowerbound, int) and me_sad_lowerbound is not None:
       raise TypeError("Oyster.Basic: me_sad_lowerbound has to be a real number or None!")
    me_sad_upperbound_scale = 1.008813680481376593785917212998847e-4
    me_sad_upperbound_multiplier = 2.850430470333669346825602033848576e-1
    me_sad_lowerbound_alpha = 1.660188324841596071680847806086676e-2
    me_sad_lowerbound_beta = 3.584988203141424006506363885606282e-1
    _init()
    if superclip is not None:
        superclip = superclip.SetFieldBased(0)
    if me_sad_upperbound is None:
        me_sad_upperbound = ConvexAttenuate(sad, me_sad_upperbound_scale, me_sad_upperbound_multiplier)
    if me_sad_lowerbound is None:
        me_sad_lowerbound = ConcaveAttenuate(me_sad_upperbound, me_sad_lowerbound_alpha, me_sad_lowerbound_beta)
    return _basic(clip.SetFieldBased(0), superclip, radius, pel, sad, me_sad_upperbound, me_sad_lowerbound)