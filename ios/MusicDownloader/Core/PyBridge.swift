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

    /// 모든 진입점은 PyThread 단일 스레드로 직렬화된다. 직접 호출 금지.
    private static func startLocked() throws {
        if started { return }
        // 번들에 딸려온 .pyc 를 iOS 인터프리터가 신뢰하지 않게 한다.
        // mac 에서 생성된 바이트코드를 그대로 실행하다 죽을 수 있어, 생성 자체를 끈다.
        setenv("PYTHONDONTWRITEBYTECODE", "1", 1)
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
        // 최초 접촉이므로 Py_Initialize 도 이 스레드에서 일어난다.
        setenv("PYTHON_LIBRARY", framework, 1)
        try PythonLibrary.useLibrary(at: framework)
        try PythonLibrary.loadLibrary()

        if !app.isEmpty {
            Python.import("sys").path.append(app)
        }
        _ = Python.import("yt_dlp")
        started = true
    }

    static func start() throws {
        try PyThread.shared.sync { try startLocked() }
    }

    static func ytdlpVersion() throws -> String {
        try PyThread.shared.sync {
            try startLocked()
            let v = Python.import("yt_dlp.version")
            return String(describing: v.__version__)
        }
    }

    /// mdl_ios.dispatch(명령 JSON) 을 호출하고 결과 JSON 문자열을 받는다.
    /// PythonKit 의 list/dict 변환은 형태가 불안정하므로 문자열로 넘겨 Swift 가 디코딩한다.
    static func callJSON(_ name: String, _ args: [String] = []) throws -> String {
        try PyThread.shared.sync {
            try startLocked()
            let payload: [String: Any] = ["fn": name, "args": args]
            let cmd = try JSONSerialization.data(withJSONObject: payload)
            let cmdStr = String(data: cmd, encoding: .utf8) ?? "{}"
            let raw = String(describing: Python.import("mdl_ios").dispatch(cmdStr))

            // Python 쪽이 {ok, data} / {ok, error} 로 감싸서 돌려준다. 예외를 던지지
            // 않기 때문이다(PythonKit 호출부는 try! 라서 예외가 프로세스가 죽임).
            guard let data = raw.data(using: .utf8),
                  let env = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
            else {
                throw PyError.python("응답 형식 이상: \(raw.prefix(200))")
            }
            if (env["ok"] as? Bool) != true {
                let msg = (env["error"] as? String) ?? "알 수 없는 오류"
                let tb = (env["trace"] as? String) ?? ""
                throw PyError.python(msg + "\n" + tb)
            }
            // data 가 문자열(파일 경로, 버전 등)이면 그대로 돌려준다. 최상위
            // string 을 dataWithJSONObject 로 감싸면 NSInvalidArgumentException 으로
            // 프로세스가 죽는다. 배열/딕셔너리만 JSON 문자열로 재인코딩한다.
            if let s = env["data"] as? String { return s }
            let inner = try JSONSerialization.data(
                withJSONObject: env["data"] ?? [], options: [.fragmentsAllowed])
            return String(data: inner, encoding: .utf8) ?? "[]"
        }
    }
}
