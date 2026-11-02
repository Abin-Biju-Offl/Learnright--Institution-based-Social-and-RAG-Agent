Add the Bot avatars from Libraries.dev to my React app.

Install:
npm install bot-avatars

Usage:
import { BotAvatar } from 'bot-avatars';

<BotAvatar type="clover" state={busy ? 'working' : 'default'} />

// A roster: each agent gets its own shape
<BotAvatar type="star" size={36} />
<BotAvatar type="flower" face="mouth" state="working" />

Props:
- type: "clover" | "flower" | "triangle" | "square" | "blob" | "ghost" | "circle" | "drop" | "star" | "droid" | "mech" | "alien" | "hexagon" | "cat" | "cloud" | "pill" | "pebble" | "puddle" — the body shape, each with its own colour
- path: a custom body outline, SVG path data in the 100×100 body box centred on (50, 50), in place of the type's own (and its antennae); the type still sets the face's place, the default colour and the label
- face: "eyes" (default) | "mouth" — the eyes alone, or eyes with a mouth
- state: "default" | "working" | "sleeping" — looking around with a jump now and then, hopping and spinning with a laugh now and then, head down with shut lids and slow breaths
- size: px or any CSS length (default 64)
- color: body colour (defaults to the type's own); brightness: 0.5–1.5, darker or lighter body (1); saturation: 0.5–2.5, duller or more vivid body (1.5; past 1.5 pushed toward the hue's most vivid shade); clover, star and cat have their own brightness and saturation (1.2 / 1.59, 1.1 / 1.84, 1.22 / 1.88); ink: face colour (auto dark or light)
- speed: multiplier on the animations; paused: freeze; seed: 0–1 offset so a row does not blink in unison
- shading: "fabric" (default: a plush faux fur — a baked pillow form under a studio light, fine strands combed down into lit locks, a silhouette of soft tufts in a haze of hairs, glossy bead eyes) | "plastic" (a per-pixel glossy material — hot spot, sheen, Fresnel rim, window reflection) | "crisp" (lit rim with a clean edge) | "smooth" (soft shadow and highlight, no edge) | "flat" (depth only); true and false mean crisp and flat
- shadow, highlight: 0–2 intensities (fabric 1.15 and 1.45, the others 0.35 and 1.3); light: degrees clockwise from the top (fabric 295, the others 300: the upper left); rim: 0–2, back light strength in fabric, Fresnel strength in plastic, rim width in crisp (fabric 0.6, the others 0.5); spread: 0.4–2.5, how far the light wraps round in fabric, highlight width in plastic, reach of the soft shading in smooth (fabric 1.6, the others 1.55); depth: 0.2–2 body thickness (0.65); roundness: 0–1, plastic and fabric's profile, 1 (default) inflated like a cushion, toward 0 a slab with soft edges
- backLight (degrees clockwise from the top; default above the toy, away from light), lightFront (0–85°, how far round to the front the key sits, 32), shine (0–2, highlights along single fibres, 0), sheen (0–2, a satin sheen over the edge, 0), backSoftness (0–1, from crisp bright hairs to an even glow, 1): fabric's light
- furLength (0.3–2.5, 1), furDensity (0.3–2, 1.6), furFuzz (0–1, the haze of hairs past the silhouette, 0.9), furClumps (0–1, gathering into tufts, 0.4), furCurl (0–1, how wavy, 0.7), furGravity (0–1, how much the pile hangs, 0.9): fabric's pile
- hat: "none" (default) | "beret" | "beanie" | "party" | "crown"; glasses: "none" (default) | "round" | "square" | "shades"; headphones, bowTie: booleans (false); accessoryColor: colour of the hat, headphones and bow tie (a soft black) — small lit 3D objects that turn with the head
- pose: { yaw, pitch, roll } in radians — holds the body there in the state's rest pose, over the animation and pointer play; for turning an avatar round by hand, usually with paused
- turn: 0–2, how far the head turns from side to side while idle (1 as the library has it, 0 faces forward)
- interactive: true by default — the eyes and head follow a pointer nearby and a click makes the avatar hop and turn round; false turns it off
- jumpHeight (body units, default 26), jumpTime (seconds in the air, 0.68), jumpStretch (stretch in the air, 0–2, 1), jumpSquash (squash on the ground, 0–2, 1.15), jumpSquashTime (seconds the landing squash takes, 0.37), jumpSquashEase (sharp | pulse | soft | bouncy), jumpGroundTime (seconds held at the deepest squash on the ground, 0.11; 0 for none), jumpGroundEase (how the weight settles through that hold: sharp | pulse | soft | bouncy, pulse), jumpRiseTime (seconds from the deepest squash back to shape, 0.33), jumpRiseEase (how it rises: sharp | pulse | soft | bouncy, pulse), jumpClickSquashTime (seconds a click's crouch and landing squash take, 0.24), jumpSpin (whole turns, 1), jumpLean (degrees, 6), jumpEvery (seconds between idle jumps, 8; 0 for none), jumpLand (seconds before or after touch-down that the landing squash begins, 0 = at contact): the idle flip and a click's jump
- theme: "auto" (default, from an ancestor data-theme / dark / light class, then prefers-color-scheme) | "dark" | "light" — the surface the avatar sits on
- whirl (0–2 strength, off by default, 1 turns it on), whirlSize (0.6–1.6), whirlWidth (0.4–2), whirlLength (0.4–1.6), whirlTilt (0.5–1.8): the motion ring round a spin, a translucent plastic tube in the body's colour

Bot avatars draws each avatar on a 2D canvas as a lit, rounded form of
a vector shape — a simple 3D head that turns, hops and flips — with a
small rig that cross-animates every state change. No WebGL, zero runtime
dependencies, React 18 or newer. It respects prefers-reduced-motion
(still pose, no motion), pauses offscreen, and carries role="img" with a
per-state label.
Docs: https://libraries.dev/bots.html

Add the Bot avatars from Libraries.dev to my React app.

Install:
npm install bot-avatars

Usage:
import { BotAvatar } from 'bot-avatars';

<BotAvatar type="clover" state={busy ? 'working' : 'default'} />

// A roster: each agent gets its own shape
<BotAvatar type="star" size={36} />
<BotAvatar type="flower" face="mouth" state="working" />

Props:
- type: "clover" | "flower" | "triangle" | "square" | "blob" | "ghost" | "circle" | "drop" | "star" | "droid" | "mech" | "alien" | "hexagon" | "cat" | "cloud" | "pill" | "pebble" | "puddle" — the body shape, each with its own colour
- path: a custom body outline, SVG path data in the 100×100 body box centred on (50, 50), in place of the type's own (and its antennae); the type still sets the face's place, the default colour and the label
- face: "eyes" (default) | "mouth" — the eyes alone, or eyes with a mouth
- state: "default" | "working" | "sleeping" — looking around with a jump now and then, hopping and spinning with a laugh now and then, head down with shut lids and slow breaths
- size: px or any CSS length (default 64)
- color: body colour (defaults to the type's own); brightness: 0.5–1.5, darker or lighter body (1); saturation: 0.5–2.5, duller or more vivid body (1.5; past 1.5 pushed toward the hue's most vivid shade); clover, star and cat have their own brightness and saturation (1.2 / 1.59, 1.1 / 1.84, 1.22 / 1.88); ink: face colour (auto dark or light)
- speed: multiplier on the animations; paused: freeze; seed: 0–1 offset so a row does not blink in unison
- shading: "fabric" (default: a plush faux fur — a baked pillow form under a studio light, fine strands combed down into lit locks, a silhouette of soft tufts in a haze of hairs, glossy bead eyes) | "plastic" (a per-pixel glossy material — hot spot, sheen, Fresnel rim, window reflection) | "crisp" (lit rim with a clean edge) | "smooth" (soft shadow and highlight, no edge) | "flat" (depth only); true and false mean crisp and flat
- shadow, highlight: 0–2 intensities (fabric 1.15 and 1.45, the others 0.35 and 1.3); light: degrees clockwise from the top (fabric 295, the others 300: the upper left); rim: 0–2, back light strength in fabric, Fresnel strength in plastic, rim width in crisp (fabric 0.6, the others 0.5); spread: 0.4–2.5, how far the light wraps round in fabric, highlight width in plastic, reach of the soft shading in smooth (fabric 1.6, the others 1.55); depth: 0.2–2 body thickness (0.65); roundness: 0–1, plastic and fabric's profile, 1 (default) inflated like a cushion, toward 0 a slab with soft edges
- backLight (degrees clockwise from the top; default above the toy, away from light), lightFront (0–85°, how far round to the front the key sits, 32), shine (0–2, highlights along single fibres, 0), sheen (0–2, a satin sheen over the edge, 0), backSoftness (0–1, from crisp bright hairs to an even glow, 1): fabric's light
- furLength (0.3–2.5, 1), furDensity (0.3–2, 1.6), furFuzz (0–1, the haze of hairs past the silhouette, 0.9), furClumps (0–1, gathering into tufts, 0.4), furCurl (0–1, how wavy, 0.7), furGravity (0–1, how much the pile hangs, 0.9): fabric's pile
- hat: "none" (default) | "beret" | "beanie" | "party" | "crown"; glasses: "none" (default) | "round" | "square" | "shades"; headphones, bowTie: booleans (false); accessoryColor: colour of the hat, headphones and bow tie (a soft black) — small lit 3D objects that turn with the head
- pose: { yaw, pitch, roll } in radians — holds the body there in the state's rest pose, over the animation and pointer play; for turning an avatar round by hand, usually with paused
- turn: 0–2, how far the head turns from side to side while idle (1 as the library has it, 0 faces forward)
- interactive: true by default — the eyes and head follow a pointer nearby and a click makes the avatar hop and turn round; false turns it off
- jumpHeight (body units, default 26), jumpTime (seconds in the air, 0.68), jumpStretch (stretch in the air, 0–2, 1), jumpSquash (squash on the ground, 0–2, 1.15), jumpSquashTime (seconds the landing squash takes, 0.37), jumpSquashEase (sharp | pulse | soft | bouncy), jumpGroundTime (seconds held at the deepest squash on the ground, 0.11; 0 for none), jumpGroundEase (how the weight settles through that hold: sharp | pulse | soft | bouncy, pulse), jumpRiseTime (seconds from the deepest squash back to shape, 0.33), jumpRiseEase (how it rises: sharp | pulse | soft | bouncy, pulse), jumpClickSquashTime (seconds a click's crouch and landing squash take, 0.24), jumpSpin (whole turns, 1), jumpLean (degrees, 6), jumpEvery (seconds between idle jumps, 8; 0 for none), jumpLand (seconds before or after touch-down that the landing squash begins, 0 = at contact): the idle flip and a click's jump
- theme: "auto" (default, from an ancestor data-theme / dark / light class, then prefers-color-scheme) | "dark" | "light" — the surface the avatar sits on
- whirl (0–2 strength, off by default, 1 turns it on), whirlSize (0.6–1.6), whirlWidth (0.4–2), whirlLength (0.4–1.6), whirlTilt (0.5–1.8): the motion ring round a spin, a translucent plastic tube in the body's colour

Bot avatars draws each avatar on a 2D canvas as a lit, rounded form of
a vector shape — a simple 3D head that turns, hops and flips — with a
small rig that cross-animates every state change. No WebGL, zero runtime
dependencies, React 18 or newer. It respects prefers-reduced-motion
(still pose, no motion), pauses offscreen, and carries role="img" with a
per-state label.
Docs: https://libraries.dev/bots.html


Add the Orb effect from Libraries.dev to my React app.

Install:
npm install thinking-orbs

Usage:
import { ThinkingOrb } from 'thinking-orbs';

<ThinkingOrb state="searching" size={64} />

Props:
- state: "working" | "searching" | "solving" | "listening" | "connecting" | "weaving" | "composing" | "breathing" | "shaping"
- size: 64 (chat-avatar scale) or 20 (inline-text scale) — each is separately tuned
- speed: multiplies the animation clock, default 1
- dark: boolean, picks the light or dark tuning
- paused: boolean, freezes the animation

Orb replaces the spinner in an AI "thinking" state with nine hand-tuned animated
states. It ships zero runtime dependencies and needs React 18 or newer.
Docs: https://libraries.dev/orbs.html


npm install metal-fx

import { MetalFx, MetalText, MetalBadge } from 'metal-fx';

<MetalFx preset="chromatic" strength={1}>
  <button>Upgrade to Pro</button>
</MetalFx>

<MetalText font="500 24px/1.2 Inter" color="#E2E2E2">Pro</MetalText>
<MetalBadge>New</MetalBadge>

npm install border-beam

import { BorderBeam } from 'border-beam';

<BorderBeam>
  <YourCard>Content</YourCard>
</BorderBeam>