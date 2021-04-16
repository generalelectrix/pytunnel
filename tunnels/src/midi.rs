use log::{error, warn};
use midir::{MidiIO, MidiInput, MidiInputConnection, MidiOutput, MidiOutputConnection, SendError};
use serde::{Deserialize, Serialize};
use simple_error::bail;
use std::{
    error::Error,
    sync::mpsc::{channel, Receiver, Sender},
    time::Duration,
};

use crate::device::Device;

/// Specification for what type of midi event.
#[derive(Debug, Copy, Clone, Hash, PartialEq, Eq, Serialize, Deserialize)]
pub enum EventType {
    NoteOn,
    NoteOff,
    ControlChange,
}

/// A specification of a midi mapping.
#[derive(Debug, Copy, Clone, Hash, PartialEq, Eq, Serialize, Deserialize)]
pub struct Mapping {
    pub event_type: EventType,
    pub channel: u8,
    pub control: u8,
}

/// Helper constructor for a note on mapping.
pub const fn note_on(channel: u8, control: u8) -> Mapping {
    Mapping {
        event_type: EventType::NoteOn,
        channel,
        control,
    }
}

/// Helper constructor for a note off mapping.
pub const fn note_off(channel: u8, control: u8) -> Mapping {
    Mapping {
        event_type: EventType::NoteOff,
        channel,
        control,
    }
}

/// Helper constructor - most controls are on channel 0.
pub const fn note_on_ch0(control: u8) -> Mapping {
    note_on(0, control)
}

/// Helper constructor - other relevant special case is channel 1.
pub const fn note_on_ch1(control: u8) -> Mapping {
    note_on(1, control)
}

/// Helper constructor for a control change mapping.
pub const fn cc(channel: u8, control: u8) -> Mapping {
    Mapping {
        event_type: EventType::ControlChange,
        channel,
        control,
    }
}

/// Helper constructor - most controls are on channel 0.
pub const fn cc_ch0(control: u8) -> Mapping {
    cc(0, control)
}

/// A fully-specified midi event.
#[derive(Debug, Copy, Clone, Serialize, Deserialize)]
pub struct Event {
    pub mapping: Mapping,
    pub value: u8,
}

/// Helper constructor for a midi event.
pub const fn event(mapping: Mapping, value: u8) -> Event {
    Event { mapping, value }
}

#[allow(dead_code)]
// Return the available ports as descriptive strings.
pub fn list_ports() -> Result<(String, String), Box<dyn Error>> {
    let input = MidiInput::new("tunnels")?;
    let inputs = input
        .ports()
        .iter()
        .filter_map(|p| input.port_name(p).ok())
        .collect::<Vec<String>>()
        .join("\n");
    let output = MidiOutput::new("tunnels")?;
    let outputs = output
        .ports()
        .iter()
        .filter_map(|p| output.port_name(p).ok())
        .collect::<Vec<String>>()
        .join("\n");
    Ok((inputs, outputs))
}

fn get_named_port<T: MidiIO>(source: &T, name: &str) -> Result<T::Port, Box<dyn Error>> {
    for port in source.ports() {
        if let Ok(this_name) = source.port_name(&port) {
            if this_name == name {
                return Ok(port);
            }
        }
    }
    bail!("no port found with name {}", name);
}

pub struct Output {
    name: String,
    conn: MidiOutputConnection,
    device: Device,
}

impl Output {
    pub fn new(name: String, device: Device) -> Result<Self, Box<dyn Error>> {
        let output = MidiOutput::new("tunnels")?;
        let port = get_named_port(&output, &name)?;
        let conn = output.connect(&port, &name)?;
        Ok(Self { name, conn, device })
    }

    pub fn send(&mut self, event: Event) -> Result<(), SendError> {
        let mut msg: [u8; 3] = [0; 3];
        msg[0] = match event.mapping.event_type {
            EventType::ControlChange => 11 << 4,
            EventType::NoteOn => 9 << 4,
            EventType::NoteOff => 8 << 4,
        } + event.mapping.channel;
        msg[1] = event.mapping.control;
        msg[2] = event.value;
        self.conn.send(&msg)
    }

    pub fn send_raw(&mut self, msg: &[u8]) -> Result<(), SendError> {
        self.conn.send(msg)
    }
}

pub struct Input {
    _conn: MidiInputConnection<()>,
}

impl Input {
    pub fn new(
        name: String,
        device: Device,
        sender: Sender<(Device, Event)>,
    ) -> Result<Self, Box<dyn Error>> {
        let input = MidiInput::new("tunnels")?;
        let port = get_named_port(&input, &name)?;
        let handler_name = name.clone();

        let conn = input.connect(
            &port,
            &name,
            move |_, msg: &[u8], _| {
                let event_type = match msg[0] >> 4 {
                    8 => EventType::NoteOff,
                    9 => EventType::NoteOn,
                    11 => EventType::ControlChange,
                    other => {
                        warn!(
                            "Ignoring midi input event on {} of unimplemented type {}.",
                            handler_name, other
                        );
                        return;
                    }
                };
                let channel = msg[0] & 15;
                sender
                    .send((
                        device,
                        Event {
                            mapping: Mapping {
                                event_type,
                                channel,
                                control: msg[1],
                            },
                            value: msg[2],
                        },
                    ))
                    .unwrap();
            },
            (),
        )?;
        Ok(Input { _conn: conn })
    }
}

/// Maintain midi inputs and outputs.
/// Aggregate input messages on a channel.
/// Provide synchronous dispatch for outgoing messages based on device type.
pub struct Manager {
    inputs: Vec<Input>,
    outputs: Vec<Output>,
    send: Sender<(Device, Event)>,
    recv: Receiver<(Device, Event)>,
}

impl Manager {
    pub fn new() -> Self {
        let (send, recv) = channel();
        Self {
            inputs: Vec::new(),
            outputs: Vec::new(),
            send,
            recv,
        }
    }

    // Add a device to the manager given input and output port names.
    pub fn add_device(&mut self, spec: DeviceSpec) -> Result<(), Box<dyn Error>> {
        let input = Input::new(spec.input_port_name, spec.device, self.send.clone())?;
        let mut output = Output::new(spec.output_port_name, spec.device)?;

        // Send initialization commands to the device.
        spec.device.init_midi(&mut output)?;

        self.inputs.push(input);
        self.outputs.push(output);
        Ok(())
    }

    // Return a message if there is one pending on the receiver.
    // Wait at most timeout for the message to appear.
    pub fn receive(&self, timeout: Duration) -> Option<(Device, Event)> {
        self.recv.recv_timeout(timeout).ok()
    }

    // Send a message to the specified device type.
    // Error conditions are logged rather than returned.
    pub fn send(&mut self, device: Device, event: Event) {
        for output in &mut self.outputs {
            if output.device == device {
                if let Err(e) = output.send(event) {
                    error!("Failed to send midi event to {}: {}.", output.name, e);
                }
            }
        }
    }
}

/// Wrapper struct for the data needed to describe a device to connect to.
#[derive(Clone, Debug)]
pub struct DeviceSpec {
    pub device: Device,
    pub input_port_name: String,
    pub output_port_name: String,
}
