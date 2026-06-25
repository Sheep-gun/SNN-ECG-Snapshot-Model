set root "C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S"
set bit_file "$root/bitstreams/nexys_a7_model_s_smoke_top.bit"

if {![file exists $bit_file]} {
    error "Bitstream not found: $bit_file"
}

open_hw_manager
connect_hw_server -allow_non_jtag

set targets [get_hw_targets *]
puts "HW_TARGET_COUNT=[llength $targets]"
if {[llength $targets] < 1} {
    error "No hardware target found. Check USB cable, board power, and Digilent cable driver."
}

current_hw_target [lindex $targets 0]
open_hw_target

set devs [get_hw_devices xc7a100t*]
puts "HW_DEVICE_COUNT=[llength $devs]"
if {[llength $devs] < 1} {
    error "No xc7a100t hardware device found."
}

set dev [lindex $devs 0]
current_hw_device $dev
refresh_hw_device $dev
set_property PROGRAM.FILE $bit_file $dev
program_hw_devices $dev
refresh_hw_device $dev

puts "PROGRAMMED_DEVICE=$dev"
puts "BITSTREAM=$bit_file"
catch {puts "DONE_PROPERTY=[get_property REGISTER.CONFIG_STATUS.BITSTREAM_DONE $dev]"}
exit

