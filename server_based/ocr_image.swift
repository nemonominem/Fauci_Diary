// OCR a scanned page image with the macOS Vision framework.
//
//   swiftc -O ocr_image.swift -o ocr_vision
//   ./ocr_vision page.png out.txt
//
// Used for the pages of a release that ship as scans with no text layer (the
// prequel's page 1 is Chairman Rand Paul's analysis). Vision returns one box
// per line; this tool puts them back in reading order, including the two-column
// comparisons at the bottom of the page, where naive top-to-bottom sorting
// interleaves the left and right columns line by line.
import Foundation
import Vision
import AppKit

func fail(_ msg: String, _ code: Int32) -> Int32 {
    FileHandle.standardError.write((msg + "\n").data(using: .utf8)!)
    return code
}

func run() -> Int32 {
    let args = CommandLine.arguments
    if args.count < 3 { return fail("usage: ocr_vision <image> <out.txt>", 2) }
    let inURL = URL(fileURLWithPath: args[1])
    let outURL = URL(fileURLWithPath: args[2])
    guard let image = NSImage(contentsOf: inURL),
          let tiff = image.tiffRepresentation,
          let rep = NSBitmapImageRep(data: tiff),
          let cg = rep.cgImage else { return fail("cannot read image " + inURL.path, 1) }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    request.recognitionLanguages = ["en-US"]
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    do { try handler.perform([request]) } catch { return fail("OCR failed: \(error)", 1) }

    struct Line { let text: String; let box: CGRect }
    var lines: [Line] = []
    for o in (request.results ?? []) {
        guard let c = o.topCandidates(1).first else { continue }
        lines.append(Line(text: c.string, box: o.boundingBox))
    }
    // Reading order: top to bottom, left to right within a row
    lines.sort {
        if abs($0.box.midY - $1.box.midY) > 0.004 { return $0.box.midY > $1.box.midY }
        return $0.box.minX < $1.box.minX
    }

    // A two-column block at the foot of the page (e.g. "what he wrote
    // privately" vs "what he said publicly") has to be read column by column.
    // The block starts after the last CENTRED (full-width) line: everything
    // below it belongs to one of the two lanes.
    var splitAt = lines.count
    if lines.count > 12 {
        var i = lines.count - 1
        while i >= 0 {
            let midX = lines[i].box.midX
            if midX >= 0.45 && midX <= 0.55 { break }   // full-width line: block ends here
            i -= 1
        }
        // ...and only treat it as columns if both lanes actually have text
        let tailCandidate = Array(lines[(i + 1)...])
        if tailCandidate.count >= 4,
           tailCandidate.contains(where: { $0.box.midX < 0.45 }),
           tailCandidate.contains(where: { $0.box.midX > 0.55 }) {
            splitAt = i + 1
        }
    }
    var ordered = Array(lines[0..<splitAt])
    let tail = Array(lines[splitAt...])
    ordered += tail.filter { $0.box.midX < 0.5 }.sorted { $0.box.midY > $1.box.midY }
    ordered += tail.filter { $0.box.midX >= 0.5 }.sorted { $0.box.midY > $1.box.midY }

    // Vision returns one box per LINE and no paragraph structure: a wider gap
    // between two lines means a new paragraph. Re-insert a blank line there so
    // the transcript keeps the page's paragraphs (the diary cleaner joins
    // wrapped lines, and would otherwise produce one wall of text).
    var gaps: [CGFloat] = []
    for i in 1..<max(1, ordered.count) {
        gaps.append(ordered[i - 1].box.minY - ordered[i].box.maxY)
    }
    let median = gaps.sorted()[gaps.count / 2] ?? 0
    var out = ""
    for (i, line) in ordered.enumerated() {
        if i > 0 {
            let gap = ordered[i - 1].box.minY - line.box.maxY
            out += (gap > median * 1.6) ? "\n\n" : "\n"
        }
        out += line.text
    }
    out += "\n"
    do { try out.write(to: outURL, atomically: true, encoding: .utf8) }
    catch { return fail("cannot write \(outURL.path): \(error)", 1) }
    print("OCR: \(lines.count) lines (\(splitAt) single-column + \(lines.count - splitAt) two-column) -> \(outURL.path)")
    return 0
}

exit(run())
