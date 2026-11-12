import Foundation
import Speech
import AVFoundation

@main
struct Main {
  static func main() async {
    let args = CommandLine.arguments
    guard args.count > 1 else { print("usage: transcribe <audiofile>"); exit(1) }
    let url = URL(fileURLWithPath: args[1])
    let locale = Locale(identifier: "en-AU")

    guard await SpeechTranscriber.supportedLocales.contains(where: {
      $0.identifier(.bcp47) == locale.identifier(.bcp47) }) else {
      FileHandle.standardError.write("locale not supported\n".data(using:.utf8)!); exit(2)
    }

    let transcriber = SpeechTranscriber(locale: locale,
      transcriptionOptions: [], reportingOptions: [], attributeOptions: [])

    do {
      if let req = try await AssetInventory.assetInstallationRequest(supporting: [transcriber]) {
        FileHandle.standardError.write("downloading model...\n".data(using:.utf8)!)
        try await req.downloadAndInstall()
      }
      let analyzer = SpeechAnalyzer(modules: [transcriber])
      let file = try AVAudioFile(forReading: url)

      async let collect: Void = {
        for try await r in transcriber.results {
          print(String(r.text.characters))
          fflush(stdout)
        }
      }()

      if let last = try await analyzer.analyzeSequence(from: file) {
        try await analyzer.finalizeAndFinish(through: last)
      } else {
        try await analyzer.cancelAndFinishNow()
      }
      try await collect
    } catch {
      FileHandle.standardError.write("ERR: \(error)\n".data(using:.utf8)!); exit(3)
    }
  }
}
