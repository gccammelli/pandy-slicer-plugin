/* Clang's arm_neon.h needs __ARM_FEATURE_FMA while declaring its intrinsics.
 * Parse it first, then hide FMA from Eigen's algorithm selection. Together with
 * -ffp-contract=off this follows the non-FMA x86 reference's arithmetic.
 *
 * Eigen 5's arm64 matrix-product kernel (arch/NEON/GeneralBlockPanelKernel.h)
 * calls the fused intrinsics below whatever the macro says, where x86-64's SSE2
 * kernel multiplies and adds. Give them that arithmetic: least-squares fits such
 * as the seam placer's otherwise round differently and move toolpaths. */
#if defined(__aarch64__)
#include <arm_neon.h>
#undef __ARM_FEATURE_FMA
#undef vfmaq_n_f32
#undef vfmaq_n_f64
#undef vfmaq_laneq_f32
#undef vfmaq_laneq_f64
#define vfmaq_n_f32(c, a, b) vaddq_f32((c), vmulq_n_f32((a), (b)))
#define vfmaq_n_f64(c, a, b) vaddq_f64((c), vmulq_n_f64((a), (b)))
#define vfmaq_laneq_f32(c, a, b, lane) vaddq_f32((c), vmulq_laneq_f32((a), (b), (lane)))
#define vfmaq_laneq_f64(c, a, b, lane) vaddq_f64((c), vmulq_laneq_f64((a), (b), (lane)))

/* Eigen sums a float packet's four lanes with vaddvq_f32, pairwise: (a0+a1)+(a2+a3).
 * Its SSE2 code adds the high half onto the low one: (a0+a2)+(a1+a3). Same order here. */
static inline float pandy_vaddvq_f32(float32x4_t a)
{
    float32x2_t halves = vadd_f32(vget_low_f32(a), vget_high_f32(a));
    return vget_lane_f32(halves, 0) + vget_lane_f32(halves, 1);
}
#undef vaddvq_f32
#define vaddvq_f32(a) pandy_vaddvq_f32(a)
#endif
