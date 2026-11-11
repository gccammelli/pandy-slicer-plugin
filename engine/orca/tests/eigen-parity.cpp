/* Eigen x86-64 vs arm64 parity probe: hashes Eigen results on fixed pseudo-random inputs.
 * Build for both architectures with the engine's compilers and flags, run both, and the
 * output lines must be identical. Inside the pandy-orca-build container, from /repo:
 *   clang++-18 -O3 -DNDEBUG -std=gnu++17 -Ibuild/orca/x86_64/deps/destdir/usr/local/include/eigen3 engine/orca/tests/eigen-parity.cpp -o build/orca/probe/eigen-x86
 *   engine/orca/cxx-aarch64 -O3 -DNDEBUG -std=gnu++17 -ffp-contract=off -include engine/orca/no-fma.h -static -Ibuild/orca/aarch64/deps/destdir/usr/local/include/eigen3 engine/orca/tests/eigen-parity.cpp -o build/orca/probe/eigen-arm
 */
#include <Eigen/Dense>
#include <cstdio>
#include <cstring>
#include <cstdint>
using namespace Eigen;
static uint32_t bits(float f){uint32_t b;memcpy(&b,&f,4);return b;}
int main(){
  uint64_t rng=0x9E3779B97F4A7C15ull; auto next=[&]{rng^=rng<<13;rng^=rng>>7;rng^=rng<<17;return (float)((rng>>40)/16777216.0*200.0-100.0);};
  uint64_t h[14]; for(auto&x:h)x=1469598103934665603ull;
  auto add=[&](int k,float f){uint32_t b=bits(f);for(int i=0;i<4;i++){h[k]^=(b>>(8*i))&0xff;h[k]*=1099511628211ull;}};
  auto addd=[&](int k,double d){uint64_t b;memcpy(&b,&d,8);for(int i=0;i<8;i++){h[k]^=(b>>(8*i))&0xff;h[k]*=1099511628211ull;}};
  uint64_t rg2=0xD1B54A32D192ED03ull; auto nx=[&]{rg2^=rg2<<13;rg2^=rg2>>7;rg2^=rg2<<17;return (float)((rg2>>40)/16777216.0*200.0-100.0);};
  auto nd=[&]{rg2^=rg2<<13;rg2^=rg2>>7;rg2^=rg2<<17;return (rg2>>11)/9007199254740992.0*200.0-100.0;};
  auto fl=[&](auto&m){for(Index k=0;k<m.size();k++)m.data()[k]=nx();}; auto fd=[&](auto&m){for(Index k=0;k<m.size();k++)m.data()[k]=nd();}; // sequential: no unspecified argument evaluation order
  for(int i=0;i<1000000;i++){
    float q[9]; for(int k=0;k<9;k++)q[k]=next();
    Vector3f a(q[0],q[1],q[2]),b(q[3],q[4],q[5]),c(q[6],q[7],q[8]);
    add(0,a.squaredNorm()); add(1,a.dot(b)); add(2,a.sum()); add(3,a.norm());
    Vector3f n=(b-a).cross(c-b).normalized(); add(4,n.x());add(4,n.y());add(4,n.z());
    Matrix3f m; m<<a,b,c; Vector3f r=m*a; add(5,r.x());add(5,r.y());add(5,r.z());
    Vector2f u(q[0],q[1]),v(q[2],q[3]); add(6,u.dot(v)); add(6,u.norm());
    add(7,(a-b).cwiseAbs().maxCoeff()); add(7,a.cwiseProduct(b).sum());
    // extra groups: values come from a second RNG so the draws above are undisturbed
    Vector4f p,p2; fl(p); fl(p2);
    add(8,p.squaredNorm()); add(8,p.dot(p2)); add(8,p.sum()); add(8,p.norm());
    Vector3d d1,d2,d3; fd(d1); fd(d2); fd(d3);
    addd(9,d1.squaredNorm()); addd(9,d1.dot(d2)); addd(9,d1.sum()); addd(9,d1.norm());
    Vector3d dn=(d2-d1).cross(d3-d2).normalized(); addd(9,dn.x());addd(9,dn.y());addd(9,dn.z());
    for(int s:{5,7,16}){VectorXf x(s),y(s); for(int k=0;k<s;k++)x[k]=nx(); for(int k=0;k<s;k++)y[k]=nx();
      add(10,x.sum()); add(10,x.squaredNorm()); add(10,x.dot(y));}
    Matrix4f M4,N4; fl(M4); fl(N4);
    Vector4f w4; fl(w4); Vector4f mv=M4*w4; for(int k=0;k<4;k++)add(11,mv[k]);
    Matrix4f MM=M4*N4; for(int r=0;r<4;r++)for(int c=0;c<4;c++)add(11,MM(r,c));
    Matrix3d A3; fd(A3);
    Vector3d x3; fd(x3); Vector3d y3=A3*x3; Vector3d z3=A3.inverse()*x3;
    for(int k=0;k<3;k++){addd(12,y3[k]);addd(12,z3[k]);}
    Matrix3f L; fl(L);
    Vector3f tr,pt; fl(tr); fl(pt);
    Transform<float,3,Affine> T=Transform<float,3,Affine>::Identity(); T.linear()=L; T.translation()=tr;
    Vector3f po=T*pt; for(int k=0;k<3;k++)add(13,po[k]);
  }
  const char*n[]={"sqnorm3","dot3","sum3","norm3","crossnorm","mat3vec","vec2","misc","vec4f","vec3d","vecXf","mat4f","mat3d","affine"};
  for(int k=0;k<14;k++)printf("%s %016llx\n",n[k],(unsigned long long)h[k]);
}
