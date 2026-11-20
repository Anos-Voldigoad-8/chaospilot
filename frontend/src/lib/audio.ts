/**
 * ChaosPilot Web Audio Synthesizer
 * Warm, organic, tactile acoustic audio engine for humanized feedback.
 */

class SoundEngine {
  private ctx: AudioContext | null = null;
  public enabled: boolean = false;

  constructor() {
    const saved = typeof window !== "undefined" ? localStorage.getItem("chaospilot_sound") : null;
    this.enabled = saved === "true";
  }

  private initCtx() {
    if (!this.ctx && typeof window !== "undefined") {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
      }
    }
    if (this.ctx && this.ctx.state === "suspended") {
      void this.ctx.resume();
    }
  }

  public setEnabled(enable: boolean) {
    this.enabled = enable;
    if (enable) this.initCtx();
    if (typeof window !== "undefined") {
      localStorage.setItem("chaospilot_sound", String(enable));
    }
  }

  public playClick() {
    if (!this.enabled) return;
    this.initCtx();
    if (!this.ctx) return;

    const now = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();

    // Warm organic tactile switch click (380Hz down to 180Hz)
    osc.type = "sine";
    osc.frequency.setValueAtTime(420, now);
    osc.frequency.exponentialRampToValueAtTime(160, now + 0.035);

    gain.gain.setValueAtTime(0.06, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.035);

    osc.connect(gain);
    gain.connect(this.ctx.destination);

    osc.start(now);
    osc.stop(now + 0.035);
  }

  public playFaultAlert() {
    if (!this.enabled) return;
    this.initCtx();
    if (!this.ctx) return;

    const now = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();

    // Muted vermilion signal tone (warm triangle wave 220Hz -> 180Hz)
    osc.type = "triangle";
    osc.frequency.setValueAtTime(220, now);
    osc.frequency.setValueAtTime(180, now + 0.08);

    gain.gain.setValueAtTime(0.08, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.22);

    osc.connect(gain);
    gain.connect(this.ctx.destination);

    osc.start(now);
    osc.stop(now + 0.22);
  }

  public playRecovery() {
    if (!this.enabled) return;
    this.initCtx();
    if (!this.ctx) return;

    const now = this.ctx.currentTime;
    const osc1 = this.ctx.createOscillator();
    const osc2 = this.ctx.createOscillator();
    const gain = this.ctx.createGain();

    // Warm acoustic harmonic fifth (440Hz -> 660Hz)
    osc1.type = "sine";
    osc2.type = "sine";

    osc1.frequency.setValueAtTime(440, now);
    osc2.frequency.setValueAtTime(660, now + 0.08);

    gain.gain.setValueAtTime(0.07, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.28);

    osc1.connect(gain);
    osc2.connect(gain);
    gain.connect(this.ctx.destination);

    osc1.start(now);
    osc1.stop(now + 0.16);
    osc2.start(now + 0.08);
    osc2.stop(now + 0.28);
  }

  public playTelemetryChirp() {
    if (!this.enabled) return;
    this.initCtx();
    if (!this.ctx) return;

    const now = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();

    // Soft paper-like tactile flutter (600Hz gentle)
    osc.type = "sine";
    osc.frequency.setValueAtTime(600, now);
    osc.frequency.exponentialRampToValueAtTime(800, now + 0.03);

    gain.gain.setValueAtTime(0.04, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.03);

    osc.connect(gain);
    gain.connect(this.ctx.destination);

    osc.start(now);
    osc.stop(now + 0.03);
  }
}

export const audioEngine = new SoundEngine();
