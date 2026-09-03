import AppKit
import CoreGraphics
import Foundation

let outputDirectory = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)

func renderIcon(size: Int, filename: String) throws {
    let colorSpace = CGColorSpaceCreateDeviceRGB()
    guard let context = CGContext(
        data: nil,
        width: size,
        height: size,
        bitsPerComponent: 8,
        bytesPerRow: 0,
        space: colorSpace,
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
    ) else {
        throw NSError(domain: "BrandIcon", code: 1)
    }

    let scale = CGFloat(size) / 512
    context.clear(CGRect(x: 0, y: 0, width: size, height: size))
    context.translateBy(x: 0, y: CGFloat(size))
    context.scaleBy(x: scale, y: -scale)

    let drop = CGMutablePath()
    drop.move(to: CGPoint(x: 256, y: 24))
    drop.addCurve(
        to: CGPoint(x: 92, y: 334),
        control1: CGPoint(x: 222, y: 80),
        control2: CGPoint(x: 92, y: 220)
    )
    drop.addCurve(
        to: CGPoint(x: 256, y: 488),
        control1: CGPoint(x: 92, y: 425),
        control2: CGPoint(x: 165, y: 488)
    )
    drop.addCurve(
        to: CGPoint(x: 420, y: 334),
        control1: CGPoint(x: 347, y: 488),
        control2: CGPoint(x: 420, y: 425)
    )
    drop.addCurve(
        to: CGPoint(x: 256, y: 24),
        control1: CGPoint(x: 420, y: 220),
        control2: CGPoint(x: 290, y: 80)
    )
    drop.closeSubpath()
    context.addPath(drop)
    context.setFillColor(CGColor(red: 17 / 255, green: 135 / 255, blue: 177 / 255, alpha: 1))
    context.fillPath()

    context.setStrokeColor(CGColor(gray: 1, alpha: 1))
    context.setLineWidth(32)
    context.setLineCap(.round)

    let upperSignal = CGMutablePath()
    upperSignal.move(to: CGPoint(x: 160, y: 294))
    upperSignal.addCurve(
        to: CGPoint(x: 352, y: 294),
        control1: CGPoint(x: 213, y: 241),
        control2: CGPoint(x: 299, y: 241)
    )
    context.addPath(upperSignal)
    context.strokePath()

    let lowerSignal = CGMutablePath()
    lowerSignal.move(to: CGPoint(x: 207, y: 341))
    lowerSignal.addCurve(
        to: CGPoint(x: 305, y: 341),
        control1: CGPoint(x: 234, y: 314),
        control2: CGPoint(x: 278, y: 314)
    )
    context.addPath(lowerSignal)
    context.strokePath()

    context.setFillColor(CGColor(gray: 1, alpha: 1))
    context.fillEllipse(in: CGRect(x: 237, y: 371, width: 38, height: 38))

    guard let image = context.makeImage() else {
        throw NSError(domain: "BrandIcon", code: 2)
    }
    let representation = NSBitmapImageRep(cgImage: image)
    guard let data = representation.representation(using: .png, properties: [:]) else {
        throw NSError(domain: "BrandIcon", code: 3)
    }
    try data.write(to: outputDirectory.appendingPathComponent(filename))
}

try renderIcon(size: 256, filename: "icon.png")
try renderIcon(size: 512, filename: "icon@2x.png")
