#ifdef GL_ES
precision mediump float;
#endif

uniform vec2 u_resolution;
uniform float u_time;

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);

    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));

    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    mat2 r = mat2(0.80, -0.60, 0.60, 0.80);

    for (int i = 0; i < 5; i++) {
        v += a * noise(p);
        p = r * p * 2.05 + 11.7;
        a *= 0.52;
    }

    return v;
}

void main() {
    vec2 uv = (gl_FragCoord.xy * 2.0 - u_resolution.xy) / min(u_resolution.x, u_resolution.y);
    float t = u_time;
    float r = length(uv);
    float a = atan(uv.y, uv.x);

    vec2 warp = uv;
    warp += 0.18 * vec2(sin(a * 3.0 + t * 0.7), cos(a * 2.0 - t * 0.6));
    warp += 0.08 * vec2(sin(uv.y * 9.0 + t), cos(uv.x * 8.0 - t));

    float n = fbm(warp * 2.2 + vec2(t * 0.08, -t * 0.05));
    float rings = sin(24.0 * r - t * 4.0 + n * 5.0);
    float arms = sin(5.0 * a + 10.0 * r - t * 2.0);
    float mask = smoothstep(0.95, 0.10, r);
    float v = smoothstep(-0.25, 0.95, rings + arms * 0.45 + n * 1.2) * mask;

    vec3 deep = vec3(0.005, 0.012, 0.028);
    vec3 cyan = vec3(0.00, 0.78, 1.00);
    vec3 blue = vec3(0.02, 0.08, 0.42);
    vec3 white = vec3(0.90, 0.96, 1.00);

    vec3 col = mix(deep, blue, n);
    col = mix(col, cyan, v * 0.75);
    col = mix(col, white, pow(v, 8.0));
    col += 0.08 / (0.08 + abs(rings)) * mask;

    gl_FragColor = vec4(pow(col, vec3(0.85)), 1.0);
}

