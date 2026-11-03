/*
 * alpvm.c -- a second, independent implementation of the OpenALP
 * reference semantics, written in C from the specification text.
 *
 * Purpose: the Python runtime and its tests were written together, so
 * they cannot tell us whether DETERMINISTIC_SEMANTICS.md and
 * CANONICAL_ENCODING.md are implementable from the prose alone. This
 * implementation exists to answer that, by reproducing the recorded
 * hashes in spec/golden/vectors.json without consulting the Python.
 *
 * C was chosen deliberately: signed overflow is undefined behaviour here,
 * so a correct implementation has to take the spec's "compute modulo
 * 2^64 and reinterpret as signed" literally and do the arithmetic
 * unsigned. A language where wrapping is the default would not have
 * tested that sentence.
 *
 * No dependencies, matching the project's own stance. SHA-256 is inline.
 *
 * Build: cc -O2 -std=c99 -o alpvm alpvm.c
 * Use:   ./alpvm --artifact-hex <hex> --step-budget <n>
 * Emits: {"hash":"sha256:...","result":{...canonical...}}
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

/* ---------------------------------------------------------------- SHA-256 */

typedef struct { uint32_t h[8]; uint64_t len; uint8_t buf[64]; size_t n; } sha256_t;

static uint32_t ror(uint32_t x, int k) { return (x >> k) | (x << (32 - k)); }

static const uint32_t K[64] = {
0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};

static void sha256_block(sha256_t *s, const uint8_t *p) {
    uint32_t w[64], a, b, c, d, e, f, g, h, t1, t2;
    int i;
    for (i = 0; i < 16; i++)
        w[i] = (uint32_t)p[i*4] << 24 | (uint32_t)p[i*4+1] << 16 | (uint32_t)p[i*4+2] << 8 | p[i*4+3];
    for (; i < 64; i++) {
        uint32_t s0 = ror(w[i-15],7) ^ ror(w[i-15],18) ^ (w[i-15] >> 3);
        uint32_t s1 = ror(w[i-2],17) ^ ror(w[i-2],19) ^ (w[i-2] >> 10);
        w[i] = w[i-16] + s0 + w[i-7] + s1;
    }
    a=s->h[0];b=s->h[1];c=s->h[2];d=s->h[3];e=s->h[4];f=s->h[5];g=s->h[6];h=s->h[7];
    for (i = 0; i < 64; i++) {
        t1 = h + (ror(e,6)^ror(e,11)^ror(e,25)) + ((e&f)^(~e&g)) + K[i] + w[i];
        t2 = (ror(a,2)^ror(a,13)^ror(a,22)) + ((a&b)^(a&c)^(b&c));
        h=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
    }
    s->h[0]+=a;s->h[1]+=b;s->h[2]+=c;s->h[3]+=d;s->h[4]+=e;s->h[5]+=f;s->h[6]+=g;s->h[7]+=h;
}

static void sha256_init(sha256_t *s) {
    s->h[0]=0x6a09e667;s->h[1]=0xbb67ae85;s->h[2]=0x3c6ef372;s->h[3]=0xa54ff53a;
    s->h[4]=0x510e527f;s->h[5]=0x9b05688c;s->h[6]=0x1f83d9ab;s->h[7]=0x5be0cd19;
    s->len = 0; s->n = 0;
}

static void sha256_update(sha256_t *s, const uint8_t *p, size_t n) {
    s->len += n;
    while (n) {
        size_t take = 64 - s->n; if (take > n) take = n;
        memcpy(s->buf + s->n, p, take);
        s->n += take; p += take; n -= take;
        if (s->n == 64) { sha256_block(s, s->buf); s->n = 0; }
    }
}

static void sha256_final(sha256_t *s, char *out_hex) {
    uint64_t bits = s->len * 8;
    uint8_t pad = 0x80;
    int i;
    sha256_update(s, &pad, 1);
    pad = 0;
    while (s->n != 56) sha256_update(s, &pad, 1);
    for (i = 7; i >= 0; i--) { uint8_t b = (uint8_t)(bits >> (i*8)); sha256_update(s, &b, 1); }
    for (i = 0; i < 8; i++) sprintf(out_hex + i*8, "%08x", s->h[i]);
    out_hex[64] = 0;
}

/* ------------------------------------------------------------------ model */

/* CANONICAL_ENCODING.md section 2 */
#define HEADER_SIZE 12
#define INSTR_SIZE  4

/* DETERMINISTIC_SEMANTICS.md section 6.2 -- the closed trap set */
#define TRAP_NONE               0
#define TRAP_STACK_UNDERFLOW    1
#define TRAP_DIV_BY_ZERO        2
#define TRAP_DIV_OVERFLOW       3
#define TRAP_INVALID_OPCODE     4
#define TRAP_IP_OUT_OF_RANGE    5
#define TRAP_BUDGET_EXCEEDED    6

static const char *trap_name(int t) {
    switch (t) {
    case TRAP_STACK_UNDERFLOW: return "trap.stack_underflow";
    case TRAP_DIV_BY_ZERO:     return "trap.div_by_zero";
    case TRAP_DIV_OVERFLOW:    return "trap.div_overflow";
    case TRAP_INVALID_OPCODE:  return "trap.invalid_opcode";
    case TRAP_IP_OUT_OF_RANGE: return "trap.ip_out_of_range";
    case TRAP_BUDGET_EXCEEDED: return "trap.step_budget_exceeded";
    default: return "";
    }
}

/* Section 4.2: compute modulo 2^64, then reinterpret as signed. Doing this
 * with int64_t directly would be undefined behaviour in C, which is
 * exactly why the spec says it this way. */
static int64_t wrap_add(int64_t a, int64_t b) { return (int64_t)((uint64_t)a + (uint64_t)b); }
static int64_t wrap_sub(int64_t a, int64_t b) { return (int64_t)((uint64_t)a - (uint64_t)b); }
static int64_t wrap_mul(int64_t a, int64_t b) { return (int64_t)((uint64_t)a * (uint64_t)b); }

typedef struct {
    int      outcome_trap;      /* 0 = halted, otherwise a trap code */
    uint64_t steps;
    int64_t *stack;
    size_t   depth;
    uint8_t *output;
    size_t   out_len;
} result_t;

/* Section 1: execution state is exactly ip, stack, output and steps. */
static result_t execute(const uint8_t *code, size_t count, uint16_t entry, uint64_t budget) {
    result_t r;
    size_t cap_stack = budget < 1024 ? 1024 : (size_t)budget + 8;  /* 3.4: depth <= budget */
    size_t cap_out   = 1024;
    uint64_t steps = 0;
    size_t depth = 0, out_len = 0;
    int64_t *stack = malloc(cap_stack * sizeof(int64_t));
    uint8_t *out = malloc(cap_out);
    uint32_t ip = entry;
    int halted = 0, trap = TRAP_NONE;

    memset(&r, 0, sizeof r);

    while (steps < budget) {
        uint8_t op, a;
        if (ip >= count) { trap = TRAP_IP_OUT_OF_RANGE; break; }   /* 1.8 */
        op = code[ip * INSTR_SIZE];
        a  = code[ip * INSTR_SIZE + 1];
        ip += 1;                                                   /* 1.5 */
        steps += 1;                                                /* 1.4 */

        /* Section 2.3: top of stack is the RIGHT operand. */
        switch (op) {
        case 0x00: break;                                          /* NOP */
        case 0x01:                                                 /* PUSH_CONST */
            /* 4.6: operand is a signed byte, widened to 64 bits. */
            stack[depth++] = (int64_t)(int8_t)a;
            break;
        case 0x02: case 0x03: case 0x04: case 0x05: {              /* ADD SUB MUL DIV */
            int64_t rhs, lhs;
            if (depth < 2) { trap = TRAP_STACK_UNDERFLOW; goto done; }
            rhs = stack[--depth];
            lhs = stack[--depth];
            if (op == 0x02) stack[depth++] = wrap_add(lhs, rhs);
            else if (op == 0x03) stack[depth++] = wrap_sub(lhs, rhs);
            else if (op == 0x04) stack[depth++] = wrap_mul(lhs, rhs);
            else {
                if (rhs == 0) { trap = TRAP_DIV_BY_ZERO; goto done; }        /* 4.4 */
                if (lhs == INT64_MIN && rhs == -1) { trap = TRAP_DIV_OVERFLOW; goto done; } /* 4.5 */
                stack[depth++] = lhs / rhs;   /* 4.3: C99 truncates toward zero */
            }
            break;
        }
        case 0x06: ip = a; break;                                  /* JMP: 2.5 index */
        case 0x07: {                                               /* JZ: 2.6 always pops */
            int64_t v;
            if (depth < 1) { trap = TRAP_STACK_UNDERFLOW; goto done; }
            v = stack[--depth];
            if (v == 0) ip = a;
            break;
        }
        case 0x08: halted = 1; break;                              /* HALT: 1.6 */
        case 0x09:                                                 /* DUP */
            if (depth < 1) { trap = TRAP_STACK_UNDERFLOW; goto done; }
            stack[depth] = stack[depth-1]; depth++;
            break;
        case 0x0A:                                                 /* POP */
            if (depth < 1) { trap = TRAP_STACK_UNDERFLOW; goto done; }
            depth--;
            break;
        case 0x0B: {                                               /* PRINT_CHAR */
            int64_t v;
            if (depth < 1) { trap = TRAP_STACK_UNDERFLOW; goto done; }
            v = stack[--depth];
            if (out_len == cap_out) { cap_out *= 2; out = realloc(out, cap_out); }
            /* 4.7: low 8 bits, unsigned. Total, never traps. */
            out[out_len++] = (uint8_t)((uint64_t)v & 0xFF);
            break;
        }
        default: trap = TRAP_INVALID_OPCODE; goto done;            /* 1.9 */
        }
        if (halted) break;
    }
    if (!halted && trap == TRAP_NONE) trap = TRAP_BUDGET_EXCEEDED;  /* 1.7 */

done:
    r.outcome_trap = trap;
    r.steps = steps;
    r.stack = stack;
    r.depth = depth;
    r.output = out;
    r.out_len = out_len;
    return r;
}

/* ------------------------------------------------- canonical JSON output */

/* Keys are emitted already sorted by code point, per section 1 of
 * CANONICAL_ENCODING.md. No whitespace. */
static void emit_result(char *buf, size_t cap, const result_t *r) {
    size_t n = 0, i;
    n += snprintf(buf+n, cap-n, "{\"outcome\":\"%s\",\"output_hex\":\"",
                  r->outcome_trap ? "trap" : "halted");
    for (i = 0; i < r->out_len; i++) n += snprintf(buf+n, cap-n, "%02x", r->output[i]);
    n += snprintf(buf+n, cap-n, "\",\"result_version\":\"1\",\"stack\":[");
    for (i = 0; i < r->depth; i++)
        n += snprintf(buf+n, cap-n, "%s%lld", i ? "," : "", (long long)r->stack[i]);
    n += snprintf(buf+n, cap-n, "],\"steps\":%llu", (unsigned long long)r->steps);
    if (r->outcome_trap)
        n += snprintf(buf+n, cap-n, ",\"trap_code\":\"%s\"", trap_name(r->outcome_trap));
    snprintf(buf+n, cap-n, "}");
}

static int hexval(int c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

int main(int argc, char **argv) {
    const char *hex = NULL;
    uint64_t budget = 0;
    const char *protocol_version = "0.2";
    int module_format_version = 1;
    uint8_t *raw; size_t raw_len, i;
    uint16_t entry, count;
    result_t r;
    char result_json[1 << 16], preimage[1 << 18], digest[65];
    size_t n = 0;
    sha256_t sha;

    for (i = 1; i < (size_t)argc; i++) {
        if (!strcmp(argv[i], "--artifact-hex") && i + 1 < (size_t)argc) hex = argv[++i];
        else if (!strcmp(argv[i], "--step-budget") && i + 1 < (size_t)argc) budget = strtoull(argv[++i], NULL, 10);
        else if (!strcmp(argv[i], "--protocol-version") && i + 1 < (size_t)argc) protocol_version = argv[++i];
        else if (!strcmp(argv[i], "--module-format-version") && i + 1 < (size_t)argc) module_format_version = atoi(argv[++i]);
    }
    if (!hex || budget == 0) { fprintf(stderr, "usage: alpvm --artifact-hex HEX --step-budget N\n"); return 2; }

    raw_len = strlen(hex) / 2;
    raw = malloc(raw_len ? raw_len : 1);
    for (i = 0; i < raw_len; i++) {
        int hi = hexval(hex[i*2]), lo = hexval(hex[i*2+1]);
        if (hi < 0 || lo < 0) { fprintf(stderr, "bad hex\n"); return 2; }
        raw[i] = (uint8_t)(hi << 4 | lo);
    }

    /* CANONICAL_ENCODING.md section 2: reject, never normalize. */
    if (raw_len < HEADER_SIZE) { fprintf(stderr, "module too small\n"); return 2; }
    if (memcmp(raw, "ALP1", 4)) { fprintf(stderr, "invalid magic\n"); return 2; }
    if (raw[4] != module_format_version) { fprintf(stderr, "unsupported module version\n"); return 2; }
    if (raw[5] != 0) { fprintf(stderr, "flags must be zero\n"); return 2; }
    if (raw[6] != 0 || raw[7] != 0) { fprintf(stderr, "reserved must be zero\n"); return 2; }
    entry = (uint16_t)(raw[8] | raw[9] << 8);
    count = (uint16_t)(raw[10] | raw[11] << 8);
    if (raw_len != (size_t)HEADER_SIZE + (size_t)count * INSTR_SIZE) {
        fprintf(stderr, "non-canonical length\n"); return 2;
    }

    r = execute(raw + HEADER_SIZE, count, entry, budget);
    emit_result(result_json, sizeof result_json, &r);

    /* Section 5: artifact_hex, preimage_version, profile, result -- sorted. */
    n += snprintf(preimage+n, sizeof(preimage)-n, "{\"artifact_hex\":\"");
    for (i = 0; i < raw_len; i++) n += snprintf(preimage+n, sizeof(preimage)-n, "%02x", raw[i]);
    n += snprintf(preimage+n, sizeof(preimage)-n,
        "\",\"preimage_version\":\"1\",\"profile\":{\"module_format_version\":%d,"
        "\"profile_version\":\"1\",\"protocol_version\":\"%s\",\"step_budget\":%llu},\"result\":",
        module_format_version, protocol_version, (unsigned long long)budget);
    n += snprintf(preimage+n, sizeof(preimage)-n, "%s}", result_json);

    sha256_init(&sha);
    sha256_update(&sha, (const uint8_t *)preimage, n);
    sha256_final(&sha, digest);

    printf("{\"hash\":\"sha256:%s\",\"result\":%s}\n", digest, result_json);
    return 0;
}
