my $first = 0;
my $in = 0;
while(<>) {
    if (/^## / && !$first) {
        $first = 1;
        $in = 1;
        print;
        next;
    }
    if (/^## / && $first) {
        exit;
    }
    print if $in;
}
