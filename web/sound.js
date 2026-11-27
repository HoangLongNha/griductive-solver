// Griductive sound: effects are synthesised with the Web Audio API, except the light switch
// and the bulb buzz, which use short recordings (web/assets/audio, see CREDITS.md).
// Recipes take (context, destination, startTime).
(function () {
  "use strict";

  const STORE_KEY = "griductive.sound.v1";
  const MASTER_LEVEL = 0.8;
  const MUSIC_LEVEL = 0.3;

  /* ---------- building blocks ---------- */

  const noiseBuffers = new WeakMap();
  function noiseBuffer(c) {
    let buf = noiseBuffers.get(c);
    if (!buf) {
      buf = c.createBuffer(1, c.sampleRate * 2, c.sampleRate);
      const data = buf.getChannelData(0);
      for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
      noiseBuffers.set(c, buf);
    }
    return buf;
  }

  // Attack/decay envelope on a gain param (exponential tail, never reaching zero exactly).
  function envelope(param, t, attack, peak, decay) {
    param.setValueAtTime(0.0001, t);
    param.linearRampToValueAtTime(peak, t + attack);
    param.exponentialRampToValueAtTime(0.0001, t + attack + decay);
  }

  function tone(c, out, t, { type = "sine", freq, freqEnd, attack = 0.004, peak = 0.2, dur = 0.2 }) {
    const osc = c.createOscillator();
    const gain = c.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, t);
    if (freqEnd) osc.frequency.exponentialRampToValueAtTime(freqEnd, t + attack + dur);
    envelope(gain.gain, t, attack, peak, dur);
    osc.connect(gain).connect(out);
    osc.start(t);
    osc.stop(t + attack + dur + 0.05);
    return osc;
  }

  function noise(c, out, t, { filter = "bandpass", freq = 1000, freqEnd, q = 1, attack = 0.005, peak = 0.2, dur = 0.1 }) {
    const src = c.createBufferSource();
    src.buffer = noiseBuffer(c);
    src.loop = true;
    const biquad = c.createBiquadFilter();
    biquad.type = filter;
    biquad.frequency.setValueAtTime(freq, t);
    if (freqEnd) biquad.frequency.exponentialRampToValueAtTime(freqEnd, t + attack + dur);
    biquad.Q.value = q;
    const gain = c.createGain();
    envelope(gain.gain, t, attack, peak, dur);
    src.connect(biquad).connect(gain).connect(out);
    src.start(t, Math.random());
    src.stop(t + attack + dur + 0.05);
  }

  /* ---------- recorded samples (web/assets/audio, see CREDITS.md) ---------- */

  const SAMPLE_URLS = {
    lightSwitch: "/assets/audio/light-switch.wav",
    bulbBuzz: "/assets/audio/bulb-buzz.wav",
  };
  const samples = {};
  // Decoded with a silent offline context at page load: no audio plays before a user gesture,
  // yet the buffers are ready for the first click. Missing files fall back to synthesis.
  (function preloadSamples() {
    const Offline = window.OfflineAudioContext || window.webkitOfflineAudioContext;
    if (!Offline || !window.fetch) return;
    const decoder = new Offline(1, 1, 44100);
    Object.entries(SAMPLE_URLS).forEach(([key, url]) => {
      fetch(url)
        .then((res) => (res.ok ? res.arrayBuffer() : Promise.reject(new Error(url))))
        .then((data) => decoder.decodeAudioData(data))
        .then((buffer) => {
          samples[key] = buffer;
        })
        .catch(() => {
          /* keep the synthesised fallback */
        });
    });
  })();

  function playSample(c, out, t, buffer, level, { loop = false, stopAt } = {}) {
    const src = c.createBufferSource();
    src.buffer = buffer;
    src.loop = loop;
    const gain = c.createGain();
    gain.gain.value = level;
    src.connect(gain).connect(out);
    src.start(t);
    if (stopAt) src.stop(stopAt);
    return src;
  }

  // Fallback if bulb-buzz.wav cannot be loaded: 120 Hz family like the recording.
  function synthBuzz(c, out, t, end) {
    const body = c.createBiquadFilter();
    body.type = "bandpass";
    body.frequency.value = 500;
    body.Q.value = 1.2;
    body.connect(out);
    [[120, "sawtooth", 0.5], [240, "square", 0.15], [480, "sawtooth", 0.08]].forEach(([f, type, level]) => {
      const osc = c.createOscillator();
      osc.type = type;
      osc.frequency.setValueAtTime(f, t);
      osc.frequency.linearRampToValueAtTime(f * 0.94, end);
      const g = c.createGain();
      g.gain.value = level;
      osc.connect(g).connect(body);
      osc.start(t + 0.03);
      osc.stop(end + 0.05);
    });
  }

  // Lights-off flicker, shared with the CSS keyframes of .briefing-lights-off (opacity = 1 - light).
  // [seconds, light level 0..1]
  const LIGHTS_OFF_SECONDS = 2.3;
  const LIGHTS_OFF_TIMELINE = [
    [0.0, 1], [0.5, 0.95], [0.55, 0], [0.68, 0], [0.7, 0.9], [0.85, 0.7], [0.88, 0.95], [1.05, 0.85],
    [1.08, 0], [1.18, 0], [1.2, 0.8], [1.32, 0.75], [1.34, 0], [1.52, 0], [1.55, 0.55], [1.75, 0.45],
    [1.78, 0.6], [1.95, 0.5], [2.25, 0], [2.3, 0],
  ];

  /* ---------- recipes ---------- */

  const knock = (c, out, t, peak = 0.35) => {
    tone(c, out, t, { freq: 190, freqEnd: 120, dur: 0.09, peak });
    noise(c, out, t, { freq: 900, q: 2, dur: 0.04, peak: peak * 0.55 });
  };

  const stamp = (c, out, t, weight = 1) => {
    tone(c, out, t, { freq: 115, freqEnd: 46, dur: 0.26, peak: 0.6 * weight });
    noise(c, out, t, { filter: "lowpass", freq: 1100, dur: 0.07, peak: 0.4 * weight });
    tone(c, out, t + 0.005, { type: "triangle", freq: 230, freqEnd: 150, dur: 0.07, peak: 0.22 * weight });
  };

  const switchClick = (c, out, t) => {
    noise(c, out, t, { filter: "highpass", freq: 2200, dur: 0.02, peak: 0.4 });
    tone(c, out, t, { type: "square", freq: 950, dur: 0.012, peak: 0.06 });
  };

  const whoosh = (c, out, t, peak = 0.55, dur = 0.45) =>
    noise(c, out, t, { freq: 320, freqEnd: 1800, q: 0.8, attack: dur * 0.35, dur: dur * 0.65, peak });

  // Old-telephone bell: two struck tones, tremoloed by the clapper (~22 Hz).
  const ring = (c, out, t, dur) => {
    const tremolo = c.createGain();
    tremolo.gain.value = 0;
    const lfo = c.createOscillator();
    lfo.type = "square";
    lfo.frequency.value = 22;
    const lfoDepth = c.createGain();
    lfoDepth.gain.value = 0.5;
    const bias = c.createConstantSource();
    bias.offset.value = 0.5;
    lfo.connect(lfoDepth).connect(tremolo.gain);
    bias.connect(tremolo.gain);
    tremolo.connect(out);
    [1250, 1580].forEach((f) => tone(c, tremolo, t, { freq: f, attack: 0.01, dur, peak: 0.16 }));
    [lfo, bias].forEach((n) => {
      n.start(t);
      n.stop(t + dur + 0.1);
    });
  };

  const RECIPES = {
    click: (c, out, t) => {
      noise(c, out, t, { freq: 3000, q: 1.2, dur: 0.03, peak: 0.45 });
      tone(c, out, t, { type: "triangle", freq: 1800, dur: 0.02, peak: 0.04 });
    },
    paper: (c, out, t) => {
      noise(c, out, t, { freq: 1900, freqEnd: 850, q: 0.9, attack: 0.04, dur: 0.24, peak: 0.5 });
      noise(c, out, t + 0.12, { freq: 2600, freqEnd: 1400, q: 1.1, attack: 0.02, dur: 0.12, peak: 0.25 });
    },
    whoosh: (c, out, t) => whoosh(c, out, t),
    stamp: (c, out, t) => stamp(c, out, t),
    notProvable: (c, out, t) => {
      knock(c, out, t, 0.3);
      knock(c, out, t + 0.13, 0.22);
    },
    contradicted: (c, out, t) => {
      const lp = c.createBiquadFilter();
      lp.type = "lowpass";
      lp.frequency.value = 650;
      lp.connect(out);
      [98, 104].forEach((f) => tone(c, lp, t, { type: "sawtooth", freq: f, attack: 0.01, dur: 0.42, peak: 0.13 }));
      knock(c, out, t, 0.3);
    },
    phone: (c, out, t) => {
      ring(c, out, t, 0.38);
      ring(c, out, t + 0.55, 0.38);
    },
    typewriter: (c, out, t) => {
      [0, 0.08, 0.17, 0.24, 0.35].forEach((d, i) => {
        noise(c, out, t + d, { freq: 3400, q: 0.9, dur: 0.025, peak: 0.24 + (i % 2) * 0.05 });
        tone(c, out, t + d, { type: "square", freq: 140 + i * 9, dur: 0.02, peak: 0.04 });
      });
      tone(c, out, t + 0.5, { freq: 2093, attack: 0.002, dur: 0.9, peak: 0.1 });
      tone(c, out, t + 0.5, { freq: 4186, attack: 0.002, dur: 0.5, peak: 0.03 });
    },
    deduce: (c, out, t) => {
      whoosh(c, out, t, 0.4, 0.4);
      [1568, 2349].forEach((f, i) => tone(c, out, t + 0.25 + i * 0.07, { freq: f, dur: 1.1, peak: 0.11 }));
    },
    // Warm "case closed" chord: C3 G3 B3 D4 E4 (Cmaj9), rolled like a piano.
    solved: (c, out, t) => {
      const lp = c.createBiquadFilter();
      lp.type = "lowpass";
      lp.frequency.value = 2600;
      lp.connect(out);
      [130.81, 196.0, 246.94, 293.66, 329.63].forEach((f, i) => {
        tone(c, lp, t + i * 0.06, { type: "triangle", freq: f, attack: 0.01, dur: 1.8, peak: 0.12 });
        tone(c, lp, t + i * 0.06, { freq: f * 2, attack: 0.01, dur: 0.9, peak: 0.035 });
      });
    },
    pins: (c, out, t) => {
      [0, 0.09, 0.2].forEach((d) => noise(c, out, t + d, { freq: 4200, q: 3, dur: 0.02, peak: 0.45 }));
    },
    // Lights off (2.3 s, same timeline as .briefing-lights-off in styles.css): wall-switch click,
    // then the weak bulb buzzes while it flickers, flares, dims and finally dies.
    switchOff: (c, out, t) => {
      if (samples.lightSwitch) {
        playSample(c, out, t, samples.lightSwitch, 0.6);
      } else {
        noise(c, out, t, { freq: 2600, q: 1.5, dur: 0.018, peak: 0.55 });
        tone(c, out, t, { type: "triangle", freq: 520, freqEnd: 300, dur: 0.03, peak: 0.2 });
        noise(c, out, t + 0.05, { freq: 1800, q: 1.2, dur: 0.012, peak: 0.22 });
      }

      const end = t + LIGHTS_OFF_SECONDS;
      // buzz -> light level (follows the timeline) -> small random stutter -> out
      const stutter = c.createGain();
      stutter.connect(out);
      const light = c.createGain();
      light.connect(stutter);
      const buzzLevel = samples.bulbBuzz ? 0.3 : 0.17;
      if (samples.bulbBuzz) {
        // recording holds two strong buzz bursts (~0.35 s and ~1.6 s) that land on lit moments
        const src = playSample(c, light, t + 0.03, samples.bulbBuzz, 1, { stopAt: end + 0.05 });
        src.playbackRate.setValueAtTime(1, t + 1.5);
        src.playbackRate.linearRampToValueAtTime(0.95, end); // sags as the bulb dies
      } else {
        synthBuzz(c, light, t, end);
      }
      light.gain.setValueAtTime(0.0001, t);
      LIGHTS_OFF_TIMELINE.forEach(([at, level]) => {
        light.gain.linearRampToValueAtTime(Math.max(0.0001, level * buzzLevel), t + at);
      });
      stutter.gain.setValueAtTime(1, t);
      for (let at = 0.04; at < LIGHTS_OFF_SECONDS; at += 0.02 + Math.random() * 0.03) {
        stutter.gain.setValueAtTime(Math.random() < 0.15 ? 0.25 : 0.65 + Math.random() * 0.35, t + at);
      }
      // faint tick each time the bulb catches again
      [0.7, 1.2, 1.55].forEach((at) => noise(c, out, t + at, { filter: "highpass", freq: 3500, dur: 0.01, peak: 0.07 }));
    },
    torchOn: (c, out, t) => {
      noise(c, out, t, { filter: "highpass", freq: 3500, dur: 0.015, peak: 0.28 });
      tone(c, out, t, { type: "square", freq: 2200, dur: 0.01, peak: 0.05 });
    },
    sweep: (c, out, t) => whoosh(c, out, t, 0.38, 0.6),
    // Lights back on: the same wall switch, then the bulb catches with two short buzzes,
    // glows with a brief warm buzz and settles to near silence (as an incandescent bulb does).
    lightsOn: (c, out, t) => {
      if (samples.lightSwitch) playSample(c, out, t, samples.lightSwitch, 0.6);
      else switchClick(c, out, t);
      const catchGain = c.createGain();
      catchGain.connect(out);
      const level = samples.bulbBuzz ? 0.3 : 0.17;
      if (samples.bulbBuzz) {
        const src = playSample(c, catchGain, t + 0.03, samples.bulbBuzz, 1, { stopAt: t + 0.95 });
        src.playbackRate.setValueAtTime(0.96, t);
        src.playbackRate.linearRampToValueAtTime(1, t + 0.4); // filament comes up to speed
      } else {
        synthBuzz(c, catchGain, t, t + 0.95);
      }
      const g = catchGain.gain;
      g.setValueAtTime(0.0001, t);
      [[0.04, 0.6], [0.065, 0.0001], [0.11, 0.8], [0.14, 0.1], [0.19, 1], [0.45, 0.5]].forEach(([at, v]) =>
        g.linearRampToValueAtTime(Math.max(0.0001, v * level), t + at));
      g.exponentialRampToValueAtTime(0.0001, t + 0.9);
    },
    // Closing a dossier / the ledger: paper slides back down and the folder taps shut.
    close: (c, out, t) => {
      noise(c, out, t, { freq: 2200, freqEnd: 700, q: 0.9, attack: 0.02, dur: 0.16, peak: 0.4 });
      tone(c, out, t + 0.13, { freq: 170, freqEnd: 110, dur: 0.07, peak: 0.18 });
      noise(c, out, t + 0.13, { filter: "lowpass", freq: 900, dur: 0.03, peak: 0.12 });
    },
    // Stepping back from the board: the approach whoosh in reverse.
    whooshOut: (c, out, t) =>
      noise(c, out, t, { freq: 1800, freqEnd: 320, q: 0.8, attack: 0.12, dur: 0.3, peak: 0.5 }),
    caseOpen: (c, out, t) => stamp(c, out, t, 1.15),
  };

  /* ---------- background music: slow noir jazz in D minor ---------- */

  const BEAT = 60 / 70; // 70 bpm
  const BAR = BEAT * 4;
  const midiHz = (n) => 440 * 2 ** ((n - 69) / 12);
  // 8-bar loop: Dm9 | Dm9 | Bbmaj7 | Bbmaj7 | Gm9 | Gm9 | A7(b9) | A7(b9)
  const CHORDS = [
    { pad: [53, 57, 60, 64], root: 38, fifth: 45, melody: [62, 65, 69, 72, 74] },
    { pad: [50, 53, 57, 62], root: 34, fifth: 41, melody: [62, 65, 69, 70, 74] },
    { pad: [53, 57, 58, 62], root: 43, fifth: 50, melody: [62, 65, 67, 70, 74] },
    { pad: [55, 58, 61, 64], root: 45, fifth: 52, melody: [61, 64, 67, 69, 70] },
  ];

  function seededRandom(seed) {
    let x = seed >>> 0 || 1;
    return () => {
      x ^= x << 13;
      x ^= x >>> 17;
      x ^= x << 5;
      return (x >>> 0) / 4294967296;
    };
  }

  // Soft sustained chord: slow swell in, held, gentle release.
  function pad(c, out, t, notes, length) {
    const lp = c.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 900;
    lp.connect(out);
    notes.forEach((n) => {
      [-4, 4].forEach((cents) => {
        const osc = c.createOscillator();
        osc.type = "triangle";
        osc.frequency.value = midiHz(n);
        osc.detune.value = cents;
        const g = c.createGain();
        g.gain.setValueAtTime(0.0001, t);
        g.gain.linearRampToValueAtTime(0.018, t + 1.4);
        g.gain.setValueAtTime(0.018, t + length - 0.8);
        g.gain.linearRampToValueAtTime(0.0001, t + length + 0.6);
        osc.connect(g).connect(lp);
        osc.start(t);
        osc.stop(t + length + 0.7);
      });
    });
  }

  // Upright-bass pluck: round fundamental with a short woody attack.
  function bass(c, out, t, n, peak = 0.2) {
    tone(c, out, t, { freq: midiHz(n), attack: 0.008, dur: 0.75, peak });
    tone(c, out, t, { type: "triangle", freq: midiHz(n) * 2, attack: 0.004, dur: 0.12, peak: peak * 0.25 });
  }

  // Vibraphone note: pure tone with a faint high partial and slow tremolo.
  function vibe(c, out, t, n, peak = 0.045) {
    const g = c.createGain();
    g.gain.value = 1;
    const lfo = c.createOscillator();
    lfo.frequency.value = 5.5;
    const depth = c.createGain();
    depth.gain.value = 0.25;
    lfo.connect(depth).connect(g.gain);
    g.connect(out);
    tone(c, g, t, { freq: midiHz(n), attack: 0.004, dur: 2.2, peak });
    tone(c, g, t, { freq: midiHz(n) * 4, attack: 0.002, dur: 0.35, peak: peak * 0.12 });
    lfo.start(t);
    lfo.stop(t + 2.4);
  }

  // Low string swell for tension before the loop turns around.
  function swell(c, out, t, n, length) {
    const lp = c.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 520;
    lp.connect(out);
    [-7, 7].forEach((cents) => {
      const osc = c.createOscillator();
      osc.type = "sawtooth";
      osc.frequency.value = midiHz(n);
      osc.detune.value = cents;
      const g = c.createGain();
      g.gain.setValueAtTime(0.0001, t);
      g.gain.linearRampToValueAtTime(0.022, t + length * 0.8);
      g.gain.linearRampToValueAtTime(0.0001, t + length + 0.3);
      osc.connect(g).connect(lp);
      osc.start(t);
      osc.stop(t + length + 0.4);
    });
  }

  function musicBar(c, out, t, bar, rand) {
    const step = bar % 8;
    const chord = CHORDS[Math.floor(step / 2)];
    const next = CHORDS[(Math.floor(step / 2) + 1) % CHORDS.length];
    if (step % 2 === 0) pad(c, out, t, chord.pad, BAR * 2);
    // bass: root on 1, fifth on 3; on the second bar walk chromatically into the next chord
    bass(c, out, t, chord.root);
    bass(c, out, t + BEAT * 2, chord.fifth, 0.15);
    if (step % 2 === 1) bass(c, out, t + BEAT * 3.5, next.root + 1, 0.12);
    // brushes on 2 and 4, faint swishes on the off-beats
    [1, 3].forEach((b) => noise(c, out, t + BEAT * b, { freq: 3200, q: 0.7, attack: 0.03, dur: 0.2, peak: 0.05 }));
    [0.5, 1.5, 2.5, 3.5].forEach((b) => noise(c, out, t + BEAT * b, { freq: 5000, q: 1, attack: 0.01, dur: 0.06, peak: 0.015 }));
    // sparse vibraphone line, never the same twice
    if (rand() < 0.65) {
      const count = 1 + Math.floor(rand() * 3);
      for (let i = 0; i < count; i++) {
        const offset = BEAT * (0.5 + Math.floor(rand() * 7) * 0.5);
        vibe(c, out, t + offset, chord.melody[Math.floor(rand() * chord.melody.length)]);
      }
    }
    if (step === 6) swell(c, out, t, chord.root + 12, BAR * 2);
  }

  // Live loop: schedule bars a little ahead of the playhead.
  function startMusic(c, out) {
    const bus = c.createGain();
    bus.gain.setValueAtTime(0.0001, c.currentTime);
    bus.gain.linearRampToValueAtTime(1, c.currentTime + 3);
    bus.connect(out);
    const rand = seededRandom(Date.now());
    let bar = 0;
    let nextBar = c.currentTime + 0.3;
    const timer = setInterval(() => {
      while (nextBar < c.currentTime + 1.5) {
        musicBar(c, bus, nextBar, bar, rand);
        bar += 1;
        nextBar += BAR;
      }
    }, 250);
    return () => {
      clearInterval(timer);
      bus.gain.setTargetAtTime(0.0001, c.currentTime, 0.3);
      setTimeout(() => bus.disconnect(), 3000);
    };
  }


  /* ---------- runtime ---------- */

  function loadPrefs() {
    try {
      const saved = JSON.parse(window.localStorage.getItem(STORE_KEY) || "{}");
      return { muted: saved.muted === true };
    } catch {
      return { muted: false };
    }
  }

  function savePrefs() {
    try {
      window.localStorage.setItem(STORE_KEY, JSON.stringify(prefs));
    } catch {
      /* preference simply is not remembered */
    }
  }

  const prefs = loadPrefs();
  const listeners = new Set();
  let ctx = null;
  let master = null;
  let musicBus = null;
  let stopMusic = null;

  // Browsers only allow audio after a user gesture, so the context is created lazily.
  function ensureContext() {
    if (!ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return null;
      ctx = new AudioCtx();
      master = ctx.createGain();
      master.gain.value = prefs.muted ? 0 : MASTER_LEVEL;
      master.connect(ctx.destination);
      musicBus = ctx.createGain();
      musicBus.gain.value = MUSIC_LEVEL;
      musicBus.connect(master);
    }
    if (ctx.state === "suspended") ctx.resume();
    return ctx;
  }

  function syncMusic() {
    if (!ctx) return;
    if (!prefs.muted && !stopMusic) stopMusic = startMusic(ctx, musicBus);
    if (prefs.muted && stopMusic) {
      stopMusic();
      stopMusic = null;
    }
  }

  function unlock() {
    if (ensureContext()) syncMusic();
  }
  ["pointerdown", "keydown"].forEach((type) => window.addEventListener(type, unlock, { capture: true }));

  const api = {
    play(name, delaySec = 0) {
      const recipe = RECIPES[name];
      if (!recipe || prefs.muted) return;
      // A context created by this very click is still resuming; sounds scheduled now play
      // as soon as it runs, so the first click is not silent.
      const c = ensureContext();
      if (!c || c.state === "closed") return;
      recipe(c, master, c.currentTime + 0.01 + delaySec);
    },
    isMuted: () => prefs.muted,
    setMuted(muted) {
      prefs.muted = Boolean(muted);
      savePrefs();
      if (master) master.gain.setTargetAtTime(prefs.muted ? 0 : MASTER_LEVEL, ctx.currentTime, 0.05);
      syncMusic();
      listeners.forEach((fn) => fn(prefs.muted));
    },
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
  };

  window.GriductiveSound = api;
})();
