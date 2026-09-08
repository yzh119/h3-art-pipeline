"""Heroes III animation groups, written as keyframed bone rotations.

Meshy's rigging returns a walk and a run. Heroes III wants thirteen groups, so the
rest are authored here rather than retargeted: the original animations are short,
stylised and specific, and a motion library matches none of them.

Everything is expressed against the rig's rest pose, in degrees, per bone, in the
bone's local space. `BASE` is the combat stance every group starts from — the
original skeleton is hunched forward with its sword low, and building that once
keeps each group to the motion that distinguishes it.

Bone names are the ones Meshy's rig uses (Mixamo lineage):

    Hips  Spine02 Spine01 Spine  neck Head
    LeftShoulder LeftArm LeftForeArm LeftHand   (and Right)
    LeftUpLeg LeftLeg LeftFoot LeftToeBase      (and Right)
"""

# The stance shared by every group: weight forward, head ahead of the shoulders,
# sword arm low and across the body, knees bent.
#
# Sign convention trap: leg bones point downward, so local X runs the opposite way
# from the spine's. Positive X on RightLeg/LeftLeg bends the knee correctly (the
# foot travels back and up); negative gives a backward-bending knee. The first
# version had every lower leg negative, and the skeleton read as digitigrade.
BASE = {
    "Hips":          (-8, 0, 0),
    "Spine02":       (10, 0, 0),
    "Spine01":       (8, 0, 0),
    "Spine":         (6, 0, 0),
    "neck":          (-14, 0, 0),
    "Head":          (-10, 0, 0),
    # X is the forward/back swing, Y rolls the arm in toward the chest, Z lowers it
    # from the A-pose. The weapon arm is the Right one by convention; mirror_pose
    # moves it to the other side for a left-handed model.
    #
    # These are measured, not guessed. The blade leaves the wrist along the hand
    # bone's axis, so the stance decides where it points: the values below put the
    # tip 0.86 forward, 0.16 to the sword's own side of the body and 0.65 below
    # the hips -- the original's low carry, blade hanging down and forward.
    #
    # The side comes from Y, the roll about the arm's own axis, not from Z. Using
    # Z to swing the blade out means raising the arm, and every silhouette gets
    # wider with it: the idle went 44 px to 52, the walk 72 to 85. Y turns the
    # blade over without moving the arm, so the stance keeps its drop.
    #
    # An earlier version read "across the body" in this comment and optimised for
    # it, putting the tip 0.53 the *other* side of the midline. The hand never
    # crosses, but at a three-quarter view a blade pointing to the far side reads
    # as being held in the far hand, and since the walk keeps it on its own side
    # the sword appeared to change hands between groups. Keep the tip positive
    # here; crossing is for the middle of a swing, not for standing still.
    "RightShoulder": (0, 0, -8),
    "RightArm":      (-16, 100, -40),
    "RightForeArm":  (-30, 0, 0),
    "LeftShoulder":  (0, 0, 8),
    "LeftArm":       (-12, -10, 50),
    "LeftForeArm":   (-26, 0, 0),
    # A wide stride, not a stand. The original's idle frame is 44 px across at 80
    # tall; the earlier stance rendered 29, a narrow column that read as a figure
    # standing to attention rather than braced for a fight. Opening the legs and
    # bending both knees takes it to 40.
    "RightUpLeg":    (38, 0, -10),
    "RightLeg":      (26, 0, 0),
    "RightFoot":     (-16, 0, 0),
    "LeftUpLeg":     (-34, 0, 10),
    "LeftLeg":       (22, 0, 0),
    "LeftFoot":      (12, 0, 0),
}


def _keys(*pairs):
    """(t, delta) pairs, t normalised 0..1 across the group."""
    return list(pairs)


# Each group: how many frames the original uses, whether it loops, and the
# deltas added to BASE at each normalised time.
def _abs(**bones):
    """Absolute bone angles, converted to the delta that reaches them from BASE.

    Groups are stored as deltas so a creature reads the same across all thirteen,
    but a delta is the wrong unit whenever the stance is already doing something
    the group needs to replace rather than add to. The walk is the case: BASE
    holds a wide combat stride, the walk cycle swings the legs again, and the two
    compound into a 126-degree split -- the skeleton scissors in place instead of
    walking. Stating the walk's legs absolutely and subtracting BASE here keeps
    the cycle independent of whatever the stance is doing.
    """
    return {bone: tuple(v - BASE.get(bone, (0, 0, 0))[i] for i, v in enumerate(value))
            for bone, value in bones.items()}


# The turn faces the creature at the viewer and raises the sword, which is what
# the original's second frame does: 38-39 px wide against 82-108 tall, its
# narrowest and nearly its tallest pose.
#
# Turning the creature is a rotation of the whole model about the world vertical,
# not a bone rotation, so it lives in "yaw" rather than in the keys. Z on the hips
# was used here and does not yaw at all: measured against the direction that faces
# the camera, the stance sits at -40.7 degrees and the old keys took it to -78.8,
# turning the creature further away. Y on the hips looked right by the same
# measurement and rendered the skeleton lying on its side -- a shoulder line
# projected flat cannot tell a yaw from a fall.
_TURNED = {
    "RightArm":     (-25, 60, 10),
    "RightForeArm": (-110, 0, 0),
}


# Standing still, the blade hangs steeper than the stance alone gives it. BASE has
# to serve the swings too -- its arm position is where every attack starts from --
# so the correction lives here rather than in BASE. Changing BASE to get this
# angle cost the attacks their reach, which is the whole reason the stance and the
# groups are separate.
#
# Measured: the idle renders 48-50 px wide with this against 53-54 without, on the
# original's 44.
_CARRY = {
    "RightArm":     (-29, 30, 0),
    "RightForeArm": (30, 0, 0),
}


# The carriage the walk holds through the whole cycle, on top of the leg swing.
# The original creeps: torso pitched well forward, head ahead of the hips, sword
# carried out horizontally rather than hanging. Walking upright rendered 37-54 px
# wide against the original's 54-72, and 78-85 tall against 71-76 -- too narrow
# and too tall, which is what standing straight up does to a side view. Twice
# these values overshot to 73-91: the torso folded double and the sword swung out
# in front of it. These are the midpoint of the two measurements, and land at
# 41-53 by 71-73.
#
# The width does not come from the stride: swinging the legs 45% further moved the
# silhouette by one pixel, because at this camera angle the stride runs almost
# straight into the lens. It comes from carrying the sword out level, which is
# what the wrist entry below does.
_WALK = dict(_abs(
    # Solved absolute, not tuned as an offset: reaching this angle by adding to the
    # stance put the blade 40 degrees nose down, because the stance's inward roll
    # rotates what "forward" means for anything layered on top.
    #
    # The target is 0.45 *above* the hand, not level with it. The camera looks down
    # 30 degrees, so a blade that is level in world space projects sloping down the
    # screen; the original reads horizontal because it is angled up. Measuring the
    # tip against the hips rather than the hand hid this twice.
    RightArm=(-25, 20, -20),
    RightForeArm=(-30, 0, 0),
    RightHand=(-90, 0, 0),
    # BASE tucks the skull down for the combat stance and creeping forward on top
    # of that buries it in the ribcage: the skull's underside sits 0.02 above the
    # top of the chest during the walk against 0.10 standing still.
    #
    # Rotating the neck the other way does not lift it. The neck bone points up,
    # so turning it swings the skull forward and *down* along an arc -- measured,
    # +18 gives 0.02 clear, +34 gives -0.01 and +50 gives -0.05, all worse. The
    # value that clears the chest is negative. Reducing the spine's lean helps a
    # little; the neck does the rest.
    neck=(-25, 0, 0),
    Head=(10, 0, 0),
), **{
    "Spine02":      (5, 0, 0),
    "Spine01":      (3, 0, 0),
})


GROUPS = {
    # Walk cycle. The original's ground line moves about 5 px across this group,
    # so the feet are allowed to leave it -- unlike the idle, which the validator
    # holds to two.
    "MOVING": {
        "frames": 8, "loop": True,
        "keys": _keys(
            (0.0,   dict(_WALK, **dict(_abs(
                     RightUpLeg=(-25, 0, 0), RightLeg=(6, 0, 0), RightFoot=(6, 0, 0),
                     LeftUpLeg=(22, 0, 0), LeftLeg=(16, 0, 0), LeftFoot=(4, 0, 0)),
                     **{"LeftArm": (-18, 0, 0), "Hips": (12, 0, -5)}))),
            (0.25,  dict(_WALK, **dict(_abs(
                     RightUpLeg=(-5, 0, 0), RightLeg=(16, 0, 0), RightFoot=(0, 0, 0),
                     LeftUpLeg=(4, 0, 0), LeftLeg=(16, 0, 0), LeftFoot=(0, 0, 0)),
                     **{"Hips": (9, 0, 0)}))),
            (0.5,   dict(_WALK, **dict(_abs(
                     RightUpLeg=(22, 0, 0), RightLeg=(16, 0, 0), RightFoot=(4, 0, 0),
                     LeftUpLeg=(-25, 0, 0), LeftLeg=(6, 0, 0), LeftFoot=(6, 0, 0)),
                     **{"LeftArm": (18, 0, 0), "Hips": (12, 0, 5)}))),
            (0.75,  dict(_WALK, **dict(_abs(
                     RightUpLeg=(4, 0, 0), RightLeg=(16, 0, 0), RightFoot=(0, 0, 0),
                     LeftUpLeg=(-5, 0, 0), LeftLeg=(16, 0, 0), LeftFoot=(0, 0, 0)),
                     **{"Hips": (9, 0, 0)}))),
        ),
    },

    # Short lead-in and lead-out the engine plays around MOVING.
    "MOVE_START": {
        "frames": 2, "loop": False,
        "keys": _keys((0.0, {}), (1.0, dict(_WALK, **{
                                        "RightUpLeg": (-14, 0, 0), "RightLeg": (-4, 0, 0),
                                        "LeftUpLeg": (12, 0, 0), "LeftLeg": (18, 0, 0)}))),
    },
    "MOVE_END": {
        "frames": 2, "loop": False,
        "keys": _keys((0.0, dict(_WALK, **{
                             "RightUpLeg": (-14, 0, 0), "RightLeg": (-4, 0, 0),
                             "LeftUpLeg": (12, 0, 0), "LeftLeg": (18, 0, 0)})), (1.0, {})),
    },

    # Idle. The feet must not move: the original holds its ground line to the
    # pixel across all eight frames, and the validator checks exactly that.
    "HOLDING": {
        "frames": 8, "loop": True,
        "keys": _keys(
            (0.0,  dict(_CARRY)),
            (0.25, dict(_CARRY, **{"Spine01": (-2, 0, 0), "neck": (2, 0, 0),
                                   "RightArm": (-27, 30, 0)})),
            (0.5,  dict(_CARRY, **{"Spine01": (-3, 0, 0), "neck": (3, 0, 0),
                                   "RightArm": (-26, 30, 1)})),
            (0.75, dict(_CARRY, **{"Spine01": (-2, 0, 0), "neck": (2, 0, 0),
                                   "RightArm": (-27, 30, 0)})),
        ),
    },

    # Hover highlight. Raises the sword, which is what the original does; the feet
    # stay planted, so only the upper body moves.
    "MOUSEON": {
        "frames": 11, "loop": True,
        "keys": _keys(
            (0.0,  {}),
            (0.35, {"RightArm": (-25, 0, 20), "RightForeArm": (-20, 0, 0),
                    "LeftArm": (10, 0, 0), "Spine01": (-4, 0, 0)}),
            (0.6,  {"RightArm": (-40, 0, 35), "RightForeArm": (-30, 0, 0),
                    "LeftArm": (16, 0, 0), "Spine01": (-6, 0, 0)}),
            (0.85, {"RightArm": (-25, 0, 20), "RightForeArm": (-20, 0, 0),
                    "LeftArm": (10, 0, 0), "Spine01": (-4, 0, 0)}),
        ),
    },

    # Forward attack: wind up, strike through, recover.
    #
    # The free arm counterswings. A body swinging a weapon puts the weapon hand
    # back and the free hand forward on the wind-up, then trades them on the
    # strike; without it the figure reads as unbalanced no matter how good the
    # weapon arm is. The first version never touched the free arm at all -- it
    # measured +0.33 in front of the hips in every frame of every attack while the
    # weapon hand travelled from +0.03 to +0.42. Same sign convention as the
    # weapon arm: negative X on the upper arm carries the hand forward.
    #
    # The strike is solved in absolute angles and stored as the delta that reaches
    # them, not tuned as a delta. BASE carries a 100-degree inward roll -- that is
    # what keeps the blade on the sword's own side of the body -- and any delta
    # added on top of it has its "forward" rotated by that much. Tuning the strike
    # as an offset produced a blade that hung down through all five strike frames
    # while the original thrusts level. Absolute arm (-70, 0, -20) with the elbow
    # at -20 puts the tip 1.34 forward and 0.04 above the hips, which is level,
    # with the hand 0.50 out in front.
    #
    # The wind-up is not just the opposite sign. Measuring the hand against the
    # hips made the first version look right -- the weapon hand read +0.03 against
    # the free hand's +0.39 -- but raising an arm pulls the hand up, not back, and
    # the whole arm was reaching forward across the chest with the blade pointing
    # the way it was about to travel.
    #
    # Swinging the shoulder back instead put the hand behind and cost all the
    # height: ATTACK_FRONT collapsed from 79-103 px tall to 79-81, against the
    # original's 69-108. The original's wind-up is both back and high.
    #
    # Both at once comes from the elbow, not the shoulder. Upper arm raised, elbow
    # folded hard so the hand returns past the head. Solved against a target
    # rather than guessed a third time, then re-solved once: the first solution
    # put the tip 1.40 above the hips and overshot the other way, 79-127 px tall
    # against the original's 69-108. The wrist's Z is what trades tip height for
    # reach behind, so each attack takes a different amount of it.
    #
    # Second sign trap, after the knees. The blade leaves the wrist along the hand
    # bone's own axis -- it is a continuation of the forearm, not something the
    # wrist aims independently -- and on the upper arm bone negative X carries that
    # line forward and up. The first version struck at +25, which swung the sword
    # behind the creature. Measured tip positions, as (forward, height) from the
    # hips, for the deltas used below: (0.83, 2.42) wound up, (1.19, 1.17) at full
    # extension, (0.66, 0.27) recovered.
    "ATTACK_FRONT": {
        "frames": 8, "loop": False,
        "keys": _keys(
            (0.0,  {}),
            (0.2,  {"RightArm": (-50, 0, 15), "RightForeArm": (-110, 0, 0),
                    "RightHand": (0, 0, 80),
                    "LeftArm": (-40, 0, 0), "LeftForeArm": (-25, 0, 0),
                    "Spine02": (-14, 0, -10), "neck": (4, 0, 0)}),
            (0.45, {"RightArm": (-54, -100, 20), "RightForeArm": (10, 0, 0),
                    "RightHand": (0, 0, 0),
                    "LeftArm": (38, 0, 0), "LeftForeArm": (10, 0, 0),
                    # The torso straightens into the thrust. Leaning further
                    # forward here curled the figure up over the five strike
                    # frames -- the original drives through standing tall.
                    "Spine02": (-8, 0, 14), "Spine01": (-6, 0, 0),
                    "Hips": (2, 0, 6), "neck": (10, 0, 0), "Head": (6, 0, 0)}),
            (0.7,  {"RightArm": (-40, -55, 16), "RightForeArm": (0, 0, 0),
                    "LeftArm": (16, 0, 0),
                    "Spine02": (-4, 0, 6), "Hips": (1, 0, 3), "neck": (5, 0, 0)}),
            (1.0,  {}),
        ),
    },

    # Upward and downward attacks reuse the swing, aimed by how far the arm is
    # allowed to come down: the strike key leaves the tip at height 1.9, 1.2 and
    # 0.45 for UP, FRONT and DOWN respectively.
    "ATTACK_UP": {
        "frames": 8, "loop": False,
        "keys": _keys(
            (0.0,  {}),
            (0.2,  {"RightArm": (-50, 0, 12), "RightForeArm": (-130, 0, 0),
                    "RightHand": (0, 0, 40),
                    "LeftArm": (-48, 0, 0), "LeftForeArm": (-28, 0, 0),
                    "Spine02": (-16, 0, -8)}),
            (0.45, {"RightArm": (-85, 0, 8), "RightForeArm": (-30, 0, 0),
                    "LeftArm": (48, 0, 0), "LeftForeArm": (14, 0, 0),
                    "Spine02": (-4, 0, 12), "Hips": (-4, 0, 5), "neck": (-14, 0, 0)}),
            (0.7,  {"RightArm": (-52, 0, 12), "RightForeArm": (-15, 0, 0),
                    "LeftArm": (24, 0, 0), "Spine02": (-2, 0, 5)}),
            (1.0,  {}),
        ),
    },
    "ATTACK_DOWN": {
        "frames": 8, "loop": False,
        "keys": _keys(
            (0.0,  {}),
            (0.2,  {"RightArm": (-45, 0, 20), "RightForeArm": (-120, 0, 0),
                    "RightHand": (0, 0, 60),
                    "LeftArm": (-38, 0, 0), "LeftForeArm": (-24, 0, 0),
                    "Spine02": (-10, 0, -12)}),
            (0.45, {"RightArm": (-60, 0, 16), "RightForeArm": (45, 0, 0),
                    "LeftArm": (42, 0, 0), "LeftForeArm": (12, 0, 0),
                    "Spine02": (12, 0, 12), "Hips": (12, 0, 4),
                    "RightUpLeg": (10, 0, 0), "neck": (6, 0, 0)}),
            (0.7,  {"RightArm": (-40, 0, 16), "RightForeArm": (20, 0, 0),
                    "LeftArm": (18, 0, 0),
                    "Spine02": (8, 0, 6), "Hips": (6, 0, 2)}),
            (1.0,  {}),
        ),
    },

    # Taking a hit: knocked back, then recovering.
    "HITTED": {
        "frames": 6, "loop": False,
        "keys": _keys(
            (0.0,  {}),
            (0.3,  {"Spine02": (-22, 0, 0), "Spine01": (-12, 0, 0), "neck": (18, 0, 0),
                    "Head": (12, 0, 0), "RightArm": (-15, 0, 10), "LeftArm": (-15, 0, -10),
                    "Hips": (-8, 0, 0)}),
            (0.6,  {"Spine02": (-10, 0, 0), "neck": (8, 0, 0), "Hips": (-4, 0, 0)}),
            (1.0,  {}),
        ),
    },

    # Defending: sword raised to near-vertical in front of the body. The original's
    # parry is its tallest and one of its narrowest poses -- 36-61 px wide against
    # 82-109 tall, where the idle is 44 by 80. The first version swung the blade
    # out sideways and crouched, and came out wider than the idle and shorter.
    "DEFENCE": {
        "frames": 11, "loop": False,
        "keys": _keys(
            (0.0,  {}),
            (0.25, {"Spine02": (-6, 0, 0), "Spine01": (-4, 0, 0), "neck": (6, 0, 0),
                    "RightArm": (-25, 60, 10), "RightForeArm": (-110, 0, 0),
                    "LeftArm": (-25, 0, -25), "LeftForeArm": (-40, 0, 0),
                    "Hips": (-4, 0, 0), "RightUpLeg": (-10, 0, 0), "LeftUpLeg": (8, 0, 0),
                    "RightLeg": (-6, 0, 0), "LeftLeg": (-4, 0, 0)}),
            (0.75, {"Spine02": (-6, 0, 0), "Spine01": (-4, 0, 0), "neck": (6, 0, 0),
                    "RightArm": (-25, 60, 10), "RightForeArm": (-110, 0, 0),
                    "LeftArm": (-25, 0, -25), "LeftForeArm": (-40, 0, 0),
                    "Hips": (-4, 0, 0), "RightUpLeg": (-10, 0, 0), "LeftUpLeg": (8, 0, 0),
                    "RightLeg": (-6, 0, 0), "LeftLeg": (-4, 0, 0)}),
            (1.0,  {}),
        ),
    },

    # Collapsing. The one group where the ground line is meant to move.
    "DEATH": {
        "frames": 6, "loop": False,
        "keys": _keys(
            (0.0,  {}),
            (0.25, {"Spine02": (-18, 0, 0), "neck": (16, 0, 0), "Hips": (-10, 0, 0),
                    "RightArm": (-20, 0, 15), "LeftArm": (-20, 0, -15)}),
            (0.6,  {"Spine02": (25, 0, 0), "Spine01": (18, 0, 0), "neck": (-10, 0, 0),
                    "Hips": (35, 0, 0), "RightUpLeg": (40, 0, 0), "LeftUpLeg": (35, 0, 0),
                    "RightLeg": (70, 0, 0), "LeftLeg": (65, 0, 0),
                    "RightArm": (10, 0, -20), "LeftArm": (10, 0, 20)}),
            (1.0,  {"Spine02": (55, 0, 0), "Spine01": (30, 0, 0), "neck": (-25, 0, 0),
                    "Hips": (78, 0, 0), "RightUpLeg": (60, 0, 0), "LeftUpLeg": (55, 0, 0),
                    "RightLeg": (95, 0, 0), "LeftLeg": (90, 0, 0),
                    "RightArm": (25, 0, -35), "LeftArm": (25, 0, 35)}),
        ),
    },

    # Turning. Two frames in the original; a half-turn of the hips reads enough at
    # this size, and the engine mirrors for the other facing anyway.
    "TURN_L": {
        "frames": 2, "loop": False,
        "keys": _keys((0.0, dict(_CARRY)),
                      (1.0, dict(_CARRY, **_TURNED))),
        "yaw": [(0.0, 0.0), (1.0, -40.0)],
    },
    "TURN_R": {
        "frames": 2, "loop": False,
        "keys": _keys((0.0, dict(_CARRY, **_TURNED)),
                      (1.0, dict(_CARRY))),
        "yaw": [(0.0, -40.0), (1.0, 0.0)],
    },
}


# ---------------------------------------------------------------------------
# Per-creature character
# ---------------------------------------------------------------------------
#
# BASE and GROUPS were authored for the skeleton warrior, and sharing them across
# the roster gave the zombie a full running stride where the original shambles.
# The motion is the character: a skeleton strides, a zombie drags its feet, a lich
# barely moves below the waist.
#
# A creature supplies two things, both optional:
#
#   base       overrides merged onto BASE -- its resting stance
#   amplitude  per-group multiplier on the motion, 1.0 being the authored amount
#
# Anything not listed falls back to the shared values, so a new creature costs a
# few lines rather than thirteen groups of keyframes.

CREATURES = {
    "CSKELE": {},          # the groups were authored against it

    "CZOMBI": {
        "base": {
            # Slumped, head lolling, arms hanging heavy and forward rather than
            # carrying anything. No weapon, so the sword stance does not apply.
            "Spine02":       (16, 0, 0),
            "Spine01":       (12, 0, 0),
            "neck":          (-6, 0, 0),
            "Head":          (8, 0, -10),
            "RightShoulder": (0, 0, -4),
            "RightArm":      (-34, 8, -28),
            "RightForeArm":  (-40, 0, 0),
            "LeftShoulder":  (0, 0, 4),
            "LeftArm":       (-30, -8, 26),
            "LeftForeArm":   (-44, 0, 0),
            # Pinned rather than inherited: the skeleton's stance opened up to
            # match its original's width, and a shambling zombie should not.
            "RightUpLeg":    (10, 0, 0),
            "RightLeg":      (14, 0, 0),
            "RightFoot":     (-6, 0, 0),
            "LeftUpLeg":     (-8, 0, 0),
            "LeftLeg":       (10, 0, 0),
            "LeftFoot":      (4, 0, 0),
        },
        "amplitude": {
            "MOVING": 0.35,        # shamble, not a stride
            "MOVE_START": 0.35,
            "MOVE_END": 0.35,
            "ATTACK_FRONT": 0.65,  # a swipe, not a sword swing
            "ATTACK_UP": 0.65,
            "ATTACK_DOWN": 0.65,
            "MOUSEON": 0.5,
            "HOLDING": 1.3,        # heavier sway while idle
        },
    },
}


def creature_profile(name):
    if not name:
        return {}
    key = name.upper()
    if key.endswith(".DEF"):
        key = key[:-4]
    return CREATURES.get(key, {})


def mirror_pose(pose):
    """Swap the left and right halves of a pose.

    Meshy puts the prop in whichever hand the concept art shows, and the concept
    is not consistent about it -- the skeleton ended up left-handed. Rather than
    author every attack twice, the group deltas are written for a right-handed
    creature and mirrored when the rebind reports a left hand.

    A mirrored rotation flips its name and negates the Y and Z components. That is
    the relationship BASE already encodes between RightArm (-16, 10, -55) and
    LeftArm (-12, -10, 50).
    """
    flipped = {}
    for bone, value in pose.items():
        if bone.startswith("Left"):
            name = "Right" + bone[len("Left"):]
        elif bone.startswith("Right"):
            name = "Left" + bone[len("Right"):]
        else:
            name = bone
        flipped[name] = (value[0], -value[1], -value[2])
    return flipped


def yaw_at(group, t):
    """Degrees to rotate the whole model about the world vertical at time t.

    Bone rotations cannot do this. The hips' own axes are not the world's, so
    yawing them tips the creature over instead of turning it.
    """
    spec = GROUPS[group]
    keys = spec.get("yaw")
    if not keys:
        return 0.0
    if spec.get("loop"):
        keys = keys + [(1.0, keys[0][1])]
    before, after = keys[0], keys[-1]
    for index in range(len(keys) - 1):
        if keys[index][0] <= t <= keys[index + 1][0]:
            before, after = keys[index], keys[index + 1]
            break
    span = after[0] - before[0]
    blend = 0.0 if span <= 0 else (t - before[0]) / span
    blend = blend * blend * (3.0 - 2.0 * blend)
    return before[1] + (after[1] - before[1]) * blend


def pose_at(group, t, creature=None, mirror=False):
    """The creature's stance plus the group's interpolated delta at time t."""
    profile = creature_profile(creature)
    base_pose = dict(BASE)
    base_pose.update(profile.get("base", {}))
    if mirror:
        base_pose = mirror_pose(base_pose)
    gain = profile.get("amplitude", {}).get(group, 1.0)

    spec = GROUPS[group]
    keys = spec["keys"]
    if spec.get("loop"):
        keys = keys + [(1.0, keys[0][1])]

    if mirror:
        keys = [(time, mirror_pose(delta)) for time, delta in keys]

    before, after = keys[0], keys[-1]
    for index in range(len(keys) - 1):
        if keys[index][0] <= t <= keys[index + 1][0]:
            before, after = keys[index], keys[index + 1]
            break

    span = after[0] - before[0]
    blend = 0.0 if span <= 0 else (t - before[0]) / span
    # Smoothstep: the original animations ease rather than move linearly.
    blend = blend * blend * (3.0 - 2.0 * blend)

    pose = {}
    for bone in set(base_pose) | set(before[1]) | set(after[1]):
        base = base_pose.get(bone, (0.0, 0.0, 0.0))
        start = before[1].get(bone, (0.0, 0.0, 0.0))
        end = after[1].get(bone, (0.0, 0.0, 0.0))
        pose[bone] = tuple(
            base[axis] + gain * (start[axis] + (end[axis] - start[axis]) * blend)
            for axis in range(3)
        )
    return pose
