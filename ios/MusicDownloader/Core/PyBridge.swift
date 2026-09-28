import Foundation
import PythonKit

enum PyError: LocalizedError {
    case missingBundle(String)
    case python(String)

    var errorDescription: String? {
        switch self {
        case .missingBundle(let p): return "번들에 \(p) 없음"
        case .python(let m): return "Python 오류: \(m)"
        }
    }
}

final class PyBridge {
    private static var started = false

    static func start() throws {
        if started { return }
        let bundle = Bundle.main
        guard let home = bundle.path(forResource: "python", ofType: nil) else {
            throw PyError.missingBundle("python")
        }
        guard let framework = bundle.path(
            forResource: "Python", ofType: "framework", inDirectory: "Frameworks"
        ) else {
            throw PyError.missingBundle("Python.framework")
        }
        let app = bundle.path(forResource: "PythonApp", ofType: nil) ?? ""

        setenv("PYTHONHOME", home, 1)
        if !app.isEmpty { setenv("PYTHONPATH", app, 1) }

        // PythonKit 은 dlopen 으로 인터프리터를 찾는데, xcframework 은 app bundle
        // 안에 임베드돼 있으므로 경로를 직접 알려줘야 한다.
        setenv("PYTHON_LIBRARY", framework, 1)
        try PythonLibrary.useLibrary(at: framework)
        try PythonLibrary.loadLibrary()

        if !app.isEmpty {
            Python.import("sys").path.append(app)
        }
        _ = Python.import("yt_dlp")
        started = true
    }

    static func ytdlpVersion() throws -> String {
        try start()
        let v = Python.import("yt_dlp.version")
        return String(describing: v.__version__)
    }
}
