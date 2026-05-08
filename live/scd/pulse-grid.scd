Server.default = s = Server.local;
s.options.numOutputBusChannels = 2;
s.options.numInputBusChannels = 0;

s.waitForBoot({
    SynthDef(\_iiPulseGrid, { |out = 0, amp = 0.18, bpm = 132|
        var beat = Impulse.kr(bpm / 60);
        var div = Demand.kr(beat, 0, Dseq([1, 2, 4, 3, 2, 6, 4, 8], inf));
        var trig = Impulse.kr((bpm / 60) * div);
        var env = Decay2.kr(trig, 0.003, Demand.kr(trig, 0, Dseq([0.04, 0.08, 0.12, 0.20], inf)));
        var step = Demand.kr(trig, 0, Dseq([0, 7, 3, 10, 12, 5, 15, 2], inf));
        var freq = 36.midicps * (2 ** (step / 12));
        var tone = VarSaw.ar(freq * [1, 1.003], 0, 0.18, 0.32);
        var click = BPF.ar(WhiteNoise.ar(0.7 ! 2), freq * 12, 0.08);
        var sig = (tone + click) * env;
        sig = RLPF.ar(sig, LFNoise1.kr([0.19, 0.23]).exprange(120, 6200), 0.22);
        sig = sig + (SinOsc.ar(36.midicps * [1, 1.001]) * 0.10);
        Out.ar(out, Limiter.ar(LeakDC.ar(sig) * amp, 0.9));
    }).add;

    s.sync;
    ~_iiGroup = Group.new;
    Synth.tail(~_iiGroup, \_iiPulseGrid);
    "_ii audio running: pulse-grid.scd".postln;
});

CmdPeriod.doOnce({
    if (~_iiGroup.notNil) {
        ~_iiGroup.free;
    };
    0.exit;
});

