#include <stdio.h>

int main(int argc, char** argv)
{
#ifdef FIRST
    bool first = true;
#else
    bool first = false;
#endif

#ifdef SECOND
    bool second = true;
#else
    bool second = false;
#endif

#if THIRD > 1
    bool third = true;
#else
    bool third = false;
#endif
}
