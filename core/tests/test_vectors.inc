/* GENERATED from protocol/messages.yaml by protocol/generate.py. Do not edit by hand. */
static const struct { const char *raw, *encoded; } COBS_VECTORS[] = {
    {"00", "0101"},
    {"0000", "010101"},
    {"11220033", "0311220233"},
    {"11223344", "0511223344"},
    {"", "01"},
};
static const struct { const char *data; unsigned crc; } CRC_VECTORS[] = {
    {"313233343536373839", 0x29b1},
    {"", 0xffff},
};
static const struct { unsigned type, seq; const char *payload, *frame; } FRAME_VECTORS[] = {
    {1, 7, "0100", "0401070103d54400"},
    {3, 7, "", "050307bb3800"},
    {4, 7, "000000000000003f000000bf0000803f0000803e00004842", "030407010101010101023f010102bf0103803f0103803e01054842d18200"},
    {5, 7, "", "0505071d9200"},
    {7, 7, "", "0507077ff400"},
};
