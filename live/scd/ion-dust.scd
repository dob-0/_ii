Server.default = s = Server.local;
s.options.numOutputBusChannels = 2;
s.options.numInputBusChannels = 0;
s.options.memSize = 65536;

s.waitForBoot({
    SynthDef(\_iiDrone, { |out = 0, amp = 0.16|
        var trig = Impulse.kr(7 * LFNoise1.kr(0.07).range(0.6, 1.4));
        var root = Demand.kr(trig, 0, Dseq([33, 33, 49.5, 44, 55, 66], inf));
        var env = Decay2.kr(trig, 0.005, LFNoise1.kr(0.2).range(0.08, 0.35));
        var sig = SinOsc.ar(root * [1, 1.005], 0, 0.35);
        sig = sig + LFSaw.ar(root * [2.01, 1.99], 0, 0.12);
        sig = sig * (0.25 + env);
        sig = RLPF.ar(sig, LFNoise1.kr([0.13, 0.17]).exprange(180, 4200), 0.18);
        sig = LeakDC.ar(sig);
        Out.ar(out, Limiter.ar(sig * amp, 0.9));
    }).add;

    SynthDef(\_iiDust, { |out = 0, amp = 0.10|
        var clock = Impulse.kr(11);
        var hit = Dust.kr(8) + CoinGate.kr(0.18, clock);
        var env = Decay2.kr(hit, 0.001, TExpRand.kr(0.02, 0.18, hit));
        var freq = TExpRand.kr(190, 7200, hit);
        var sig = WhiteNoise.ar(1 ! 2);
        sig = BPF.ar(sig, freq * [1, 1.012], 0.04);
        sig = sig * env;
        sig = Pan2.ar(Mix(sig), LFNoise1.kr(1.4), amp);
        Out.ar(out, Limiter.ar(sig, 0.85));
    }).add;

    s.sync;
    ~_iiGroup = Group.new;
    Synth.tail(~_iiGroup, \_iiDrone);
    Synth.tail(~_iiGroup, \_iiDust);
    "_ii audio running: ion-dust.scd".postln;
});

CmdPeriod.doOnce({
    if (~_iiGroup.notNil) {
        ~_iiGroup.free;
    };
    0.exit;
});

