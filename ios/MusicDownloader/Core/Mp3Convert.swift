import Foundation

enum Mp3ConvertError: LocalizedError {
    case failed(Int32)

    var errorDescription: String? {
        switch self {
        case .failed(let code):
            return "MP3 변환 실패 (code=\(code))"
        }
    }
}

enum Mp3Convert {
    static func convert(src: URL, dst: URL, bitrateKbps: Int) throws {
        let rc: Int32 = src.path.withCString { s in
            dst.path.withCString { d in
                mdl_convert_to_mp3(s, d, Int32(bitrateKbps))
            }
        }
        guard rc == 0 else { throw Mp3ConvertError.failed(rc) }
    }
}
