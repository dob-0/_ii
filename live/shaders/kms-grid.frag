#ifdef GL_ES
precision mediump float;
#endif

uniform vec2 u_resolution;
uniform float u_time;

float line(float d, float w) {
    return 1.0 - smoothstep(0.0, w, abs(d));
}

void main() {
    vec2 uv = (gl_FragCoord.xy * 2.0 - u_resolution.xy) / min(u_resolution.x, u_resolution.y);
    float t = u_time;

    vec2 p = uv;
    p.y += 0.45;

    float horizon = smoothstep(0.65, -0.45, p.y);
    float depth = 1.0 / max(0.10, p.y + 1.20);
    vec2 grid = vec2(p.x * depth * 2.2, depth + t * 0.42);

    float gx = line(fract(grid.x + 0.5) - 0.5, 0.028 * depth);
    float gy = line(fract(grid.y) - 0.5, 0.020 * depth);
    float center = line(p.x, 0.010 + 0.020 * sin(t));
    float scan = line(fract((uv.y + t * 0.3) * 28.0) - 0.5, 0.05);

    float sun = smoothstep(0.42, 0.40, length(uv - vec2(0.0, 0.28)));
    sun *= 0.55 + 0.45 * step(0.18, fract((uv.y - t * 0.02) * 18.0));

    float glow = max(gx, gy) * horizon;
    vec3 col = vec3(0.004, 0.005, 0.012);
    col += sun * vec3(0.95, 0.12, 0.35);
    col += glow * vec3(0.00, 0.75, 1.00);
    col += center * vec3(1.00, 1.00, 1.00);
    col += scan * 0.035;

    gl_FragColor = vec4(col, 1.0);
}

