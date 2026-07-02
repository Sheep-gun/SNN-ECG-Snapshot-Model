set script_dir [file dirname [file normalize [info script]]]
set repo_dir [file normalize [file join $script_dir ".."]]
set bit_file [file join $repo_dir "results" "final_membrane_v2_snn" "vivado_snn_ecg_v2" "bitstream" "snn_ecg_v2_nexys_a7_top.bit"]
set out_dir [file join $repo_dir "results" "final_membrane_v2_snn" "vivado_snn_ecg_v2"]
set report_file [file join $out_dir "board_program_report.txt"]

file mkdir $out_dir

if {![file exists $bit_file]} {
    error "Bitstream not found: $bit_file"
}

set fh [open $report_file "w"]
puts $fh "SNN ECG V2 FPGA board programming report"
puts $fh "Bitstream: $bit_file"
puts $fh "Timestamp: [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"

open_hw_manager
connect_hw_server
open_hw_target

set devices [get_hw_devices]
puts $fh "Detected devices: $devices"
if {[llength $devices] == 0} {
    close $fh
    error "No hardware devices detected"
}

set selected_device ""
foreach dev $devices {
    if {[string match "*xc7a100t*" $dev] || [string match "*xc7a100*" $dev]} {
        set selected_device $dev
        break
    }
}
if {$selected_device eq ""} {
    set selected_device [lindex $devices 0]
}

current_hw_device $selected_device
refresh_hw_device -update_hw_probes false $selected_device

puts $fh "Selected device: $selected_device"
puts $fh "PART: [get_property PART $selected_device]"
puts $fh "PROGRAM.FILE before: [get_property PROGRAM.FILE $selected_device]"

set_property PROGRAM.FILE $bit_file $selected_device
program_hw_devices $selected_device
refresh_hw_device -update_hw_probes false $selected_device

puts $fh "PROGRAM.FILE after: [get_property PROGRAM.FILE $selected_device]"
puts $fh "PROGRAM.HW_CFGMEM: [get_property PROGRAM.HW_CFGMEM $selected_device]"
puts $fh "PROGRAMMED: OK"
close $fh

puts "BOARD_PROGRAM_REPORT=$report_file"
close_hw_manager
exit
