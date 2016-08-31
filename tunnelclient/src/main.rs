extern crate piston;
extern crate graphics;
extern crate glutin_window;
extern crate sdl2_window;
extern crate opengl_graphics;

use piston::window::WindowSettings;
use piston::event_loop::*;
use piston::input::*;
//use glutin_window::GlutinWindow as Window;
use sdl2_window::Sdl2Window as Window;

use std::f64::consts::PI;

use opengl_graphics::{ GlGraphics, OpenGL };

pub struct App {
    gl: GlGraphics, // OpenGL drawing backend.
    rotation: f64,   // Rotation for the square.
    marquee: f64    // marquee rotation position
}

pub struct Arc {
    level: u64,
    thickness: f32,
    hue: f32,
    sat: f32,
    val: u64,
    x: f32,
    y: f32,
    rad_x: f32,
    rad_y: f32,
    start: f32,
    stop: f32,
    rot_angle: f32
}

const TWOPI: f64 = 2.0 * PI;

impl App {
    fn render(&mut self, args: &RenderArgs) {
        use graphics::*;

        const BLACK: [f32; 4] = [0.0, 0.0, 0.0, 1.0];
        const GREEN: [f32; 4] = [0.0, 1.0, 0.0, 1.0];
        const RED:   [f32; 4] = [1.0, 0.0, 0.0, 1.0];
        const BLUE:  [f32; 4] = [0.0, 0.0, 1.0, 1.0];
        const WHITE: [f32; 4] = [1.0, 1.0, 1.0, 1.0];

        let bound = rectangle::centered([0.0, 0.0, 550.0, 340.0]);
        let rotation = self.rotation;
        let marquee = self.marquee;
        let (x, y) = ((args.width / 2) as f64,
                      (args.height / 2) as f64);

        let extrapolation = 0.3 * args.ext_dt;
        println!("{}", args.ext_dt);

        self.gl.draw(args.viewport(), |c, gl| {
            // Clear the screen.
            clear(BLACK, gl);

            let transform = c.transform.trans(x, y)
                                       .rot_rad(rotation);

            //circle_arc(RED, 20.0, 0.0, 3.141, bound, transform, gl);
            let seg_width = TWOPI / 128.0;
            for seg in 0..128 {
                if seg % 2 == 0 {
                    let start = ((seg as f64 * seg_width) + marquee + extrapolation);
                    let end = start + seg_width;
                    circle_arc(WHITE, 20.0, start, end, bound, transform, gl);
                }
            }

        });
    }

    fn update(&mut self, args: &UpdateArgs) {
        // Rotate 2 radians per second.
        self.rotation = (self.rotation + 0.0 * args.dt) % TWOPI;
        self.marquee = (self.marquee + 0.3 * args.dt) % TWOPI;
    }
}

fn main() {
    // Change this to OpenGL::V2_1 if not working.
    let opengl = OpenGL::V3_2;

    // Create an Glutin window.
    let mut window: Window = WindowSettings::new(
            "spinning-square",
            [1280, 720]
        )
        .opengl(opengl)
        .exit_on_esc(true)
        .vsync(true)
        .samples(4)
        //.fullscreen(true)
        .build()
        .unwrap();

    // Create a new game and run it.
    let mut app = App {
        gl: GlGraphics::new(opengl),
        rotation: 0.0,
        marquee: 0.0
    };

    let mut events = window.events();
    while let Some(e) = events.next(&mut window) {

        if let Some(u) = e.update_args() {
            app.update(&u);
        }

        if let Some(r) = e.render_args() {
            app.render(&r);
        }
    }
}