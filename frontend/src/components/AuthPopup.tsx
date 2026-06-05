import React, { useState, useEffect } from 'react';
import { X, ShieldAlert, Sparkles, User, LogOut, Key, Hash, Layers, Play, Check } from 'lucide-react';
import {
  loginUser,
  registerUser,
  getUserVectorStatus,
  getSession
} from '../api/client';
import type { VectorStatusResponse, SessionResponse } from '../api/client';

interface AuthPopupProps {
  isOpen: boolean;
  onClose: () => void;
  user: { id: string; username: string } | null;
  sessionId: string | null;
  onLoginSuccess: (userData: { id: string; username: string }, token: string) => void;
  onRegisterSuccess: (userData: { id: string; username: string }, token: string) => void;
  onLogout: () => void;
}

const AVAILABLE_TAGS = [
  { id: 'nature', label: '🌲 nature' },
  { id: 'meditation', label: '🧘 calming' },
  { id: 'cooking', label: '🍳 cooking' },
  { id: 'fitness', label: '🏋️ sport' },
  { id: 'gaming', label: '🎮 gaming' },
  { id: 'programming', label: '💻 education' },
  { id: 'travel', label: '✈️ lifestyle' },
  { id: 'dance', label: '💃 entertainment' }
];

export const AuthPopup: React.FC<AuthPopupProps> = ({
  isOpen,
  onClose,
  user,
  sessionId,
  onLoginSuccess,
  onRegisterSuccess,
  onLogout
}) => {
  const [tab, setTab] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Diagnostic states for logged in user
  const [vectorStatus, setVectorStatus] = useState<VectorStatusResponse | null>(null);
  const [sessionStats, setSessionStats] = useState<SessionResponse | null>(null);
  const [diagLoading, setDiagLoading] = useState(false);

  useEffect(() => {
    if (user && isOpen) {
      setDiagLoading(true);
      setError(null);

      // Fetch both vector status and session stats parallel
      Promise.all([
        getUserVectorStatus(user.id).catch(err => {
          console.error("Vector status error:", err);
          return null;
        }),
        sessionId ? getSession(sessionId).catch(err => {
          console.error("Session stats error:", err);
          return null;
        }) : Promise.resolve(null)
      ]).then(([vStatus, sStats]) => {
        setVectorStatus(vStatus);
        setSessionStats(sStats);
        setDiagLoading(false);
      });
    }
  }, [user, sessionId, isOpen]);

  if (!isOpen) return null;

  const handleTagToggle = (tagId: string) => {
    setSelectedTags(prev => {
      if (prev.includes(tagId)) {
        return prev.filter(id => id !== tagId);
      } else {
        if (prev.length >= 2) {
          // Limit to 2 tags
          return [prev[1], tagId];
        }
        return [...prev, tagId];
      }
    });
  };

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username) {
      setError('Vui lòng nhập tên đăng nhập');
      return;
    }
    setError(null);
    setLoading(true);

    try {
      if (tab === 'login') {
        const data = await loginUser(username, password);
        onLoginSuccess({ id: data.user_id, username: data.username }, data.access_token);
        onClose();
      } else {
        if (selectedTags.length !== 2) {
          setError('Vui lòng chọn chính xác 2 chủ đề quan tâm');
          setLoading(false);
          return;
        }
        const data = await registerUser(username, '', password, selectedTags);
        onRegisterSuccess({ id: data.user_id, username: data.username }, data.access_token);
        onClose();
      }
    } catch (err: any) {
      setError(err.message || 'Có lỗi xảy ra, vui lòng thử lại');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="absolute inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-end justify-center transition-all duration-300">
      <div className="absolute inset-0" onClick={onClose} />

      <div className="relative w-full max-w-md bg-zinc-900 border-t border-zinc-800 rounded-t-[32px] p-5 flex flex-col items-center gap-4 z-10 shadow-2xl animate-in slide-in-from-bottom duration-300 max-h-[90%] overflow-y-auto">

        <div className="w-12 h-1 bg-zinc-700 rounded-full mb-1 shrink-0" />

        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-full hover:bg-zinc-800 text-zinc-400 hover:text-white transition-colors"
        >
          <X size={20} />
        </button>

        {user ? (
          /* Profile Mode */
          <div className="w-full flex flex-col gap-4">

            {/* Header profile info */}
            <div className="flex items-center gap-3 bg-zinc-800/40 p-4 rounded-2xl border border-zinc-800/80">
              <div className="w-12 h-12 rounded-full bg-emerald-500 flex items-center justify-center text-zinc-950 text-xl font-bold uppercase">
                {user.username.substring(0, 2)}
              </div>
              <div className="flex flex-col">
                <span className="text-sm font-semibold text-white">@{user.username}</span>
                <span className="text-[10px] text-zinc-400">Trạng thái: Đã đăng nhập</span>
              </div>
            </div>

            {/* Diagnostics details */}
            <div className="flex flex-col gap-2.5">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-zinc-400 px-1">
                <Hash size={14} className="text-emerald-400" />
                <span>Diagnostic: Vector Sở Thích</span>
              </div>

              <div className="bg-zinc-950 border border-zinc-800/50 rounded-2xl p-4 flex flex-col gap-3">
                {diagLoading ? (
                  <div className="text-center py-6 text-xs text-zinc-500 animate-pulse">
                    Đang tải dữ liệu vector từ MongoDB Atlas...
                  </div>
                ) : (
                  <>
                    <div className="grid grid-cols-2 gap-3 text-[11px]">
                      <div className="bg-zinc-900/60 p-2.5 rounded-xl border border-zinc-800/55">
                        <span className="text-zinc-500 block mb-0.5 font-medium">Kích thước Vector</span>
                        <span className="font-mono text-emerald-400 font-bold text-xs">
                          {vectorStatus?.has_vector ? `${vectorStatus.vector_dimensions} Dimensions` : '0 Dim'}
                        </span>
                      </div>
                      <div className="bg-zinc-900/60 p-2.5 rounded-xl border border-zinc-800/55">
                        <span className="text-zinc-500 block mb-0.5 font-medium">Độ dài Vector</span>
                        <span className="font-mono text-emerald-400 font-bold text-xs">
                          {vectorStatus?.has_vector ? vectorStatus.vector_magnitude.toFixed(4) : '0.0000'}
                        </span>
                      </div>
                    </div>

                    <div className="bg-zinc-900/60 p-3 rounded-xl border border-zinc-800/55 flex flex-col gap-1">
                      <span className="text-[10px] text-zinc-500 font-medium">Chủ đề quan tâm ban đầu:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {vectorStatus?.interest_tags && vectorStatus.interest_tags.length > 0 ? (
                          vectorStatus.interest_tags.map(t => (
                            <span key={t} className="text-[9px] bg-emerald-500/10 text-emerald-300 px-2 py-0.5 rounded border border-emerald-500/20 font-medium">
                              #{t}
                            </span>
                          ))
                        ) : (
                          <span className="text-[9px] text-zinc-600">Chưa thiết lập</span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-[10px] text-zinc-400 border-t border-zinc-900 pt-2 px-1">
                      <span className="flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
                        Atlas Vector Search Ready
                      </span>
                      <span>v1.0</span>
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* Session Stats Section */}
            <div className="flex flex-col gap-2.5">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-zinc-400 px-1">
                <Layers size={14} className="text-emerald-400" />
                <span>Thống Kê Phiên Làm Việc (Session)</span>
              </div>

              <div className="bg-zinc-950 border border-zinc-800/50 rounded-2xl p-4 flex flex-col gap-2 text-[11px] text-zinc-300">
                <div className="flex justify-between py-1 border-b border-zinc-900">
                  <span className="text-zinc-500">Session ID:</span>
                  <span className="font-mono text-zinc-400">{sessionId ? `${sessionId.substring(0, 8)}...` : 'N/A'}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-zinc-900">
                  <span className="text-zinc-500">Đã xem trong phiên:</span>
                  <span className="font-semibold text-white">{sessionStats?.total_videos_watched ?? 0} videos</span>
                </div>
                <div className="flex justify-between py-1 border-b border-zinc-900">
                  <span className="text-zinc-500">Thời gian xem TB:</span>
                  <span className="font-semibold text-white">{(sessionStats?.avg_watch_duration ?? 0).toFixed(1)} giây</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-zinc-500">Tốc độ vuốt TB:</span>
                  <span className="font-semibold text-white">{(sessionStats?.avg_swipe_speed ?? 0).toFixed(0)} px/s</span>
                </div>
              </div>
            </div>

            {/* Logout button */}
            <button
              onClick={() => {
                onLogout();
                onClose();
              }}
              className="w-full mt-2 py-3 px-4 bg-rose-500/10 hover:bg-rose-500 hover:text-black text-rose-400 font-semibold rounded-2xl flex items-center justify-center gap-2 border border-rose-500/20 transition-all text-xs"
            >
              <LogOut size={16} />
              Đăng xuất phiên hiện tại
            </button>
          </div>
        ) : (
          /* Auth Form Mode */
          <div className="w-full flex flex-col gap-4">

            {/* Logo and Intro */}
            <div className="text-center shrink-0">
              <div className="flex items-center justify-center gap-2 mb-1.5 text-emerald-400">
                <Sparkles size={22} className="animate-pulse" />
                <h2 className="text-lg font-bold text-white tracking-wide">GoTouchGrass</h2>
              </div>
              <p className="text-zinc-400 text-[10px] px-4 leading-normal">
                Ứng dụng mô phỏng mạng xã hội sức khỏe số. Bảo vệ tâm lý người dùng thông qua mô hình phân tích vector tương tác.
              </p>
            </div>

            {/* Tabs toggle */}
            <div className="flex bg-zinc-950 p-1 rounded-xl border border-zinc-800/80">
              <button
                onClick={() => { setTab('login'); setError(null); }}
                className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all ${tab === 'login' ? 'bg-zinc-800 text-white' : 'text-zinc-500 hover:text-zinc-300'}`}
              >
                Đăng nhập
              </button>
              <button
                onClick={() => { setTab('register'); setError(null); }}
                className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all ${tab === 'register' ? 'bg-zinc-800 text-white' : 'text-zinc-500 hover:text-zinc-300'}`}
              >
                Tạo tài khoản mới
              </button>
            </div>

            {/* Error Message */}
            {error && (
              <div className="bg-rose-500/10 border border-rose-500/30 text-rose-300 text-[10.5px] p-2.5 rounded-xl text-center font-medium animate-shake animate-duration-200">
                {error}
              </div>
            )}

            {/* Form */}
            <form onSubmit={handleAuthSubmit} className="flex flex-col gap-3.5">

              {/* Username Input */}
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider px-1">Tên đăng nhập</label>
                <div className="relative">
                  <User className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500" size={16} />
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="nhap_username_cua_ban"
                    className="w-full bg-zinc-950 border border-zinc-800 focus:border-emerald-500 focus:outline-none py-2.5 pl-10 pr-4 text-xs rounded-xl text-white font-mono placeholder:text-zinc-700 transition-colors"
                    required
                  />
                </div>
              </div>

              {/* Password Input */}
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider px-1">Mật khẩu</label>
                <div className="relative">
                  <Key className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500" size={16} />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-zinc-950 border border-zinc-800 focus:border-emerald-500 focus:outline-none py-2.5 pl-10 pr-4 text-xs rounded-xl text-white font-mono placeholder:text-zinc-700 transition-colors"
                  />
                </div>
              </div>

              {/* Register - Tag selection onboarding */}
              {tab === 'register' && (
                <div className="flex flex-col gap-2 bg-zinc-950/40 p-3 rounded-2xl border border-zinc-900">
                  <div className="flex justify-between items-center px-1">
                    <label className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider">Chọn đúng 2 chủ đề quan tâm</label>
                    <span className="text-[9px] font-semibold font-mono text-emerald-400 bg-emerald-500/10 px-1.5 py-0.25 rounded">
                      Đã chọn: {selectedTags.length}/2
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 mt-1">
                    {AVAILABLE_TAGS.map(t => {
                      const isSelected = selectedTags.includes(t.id);
                      return (
                        <button
                          key={t.id}
                          type="button"
                          onClick={() => handleTagToggle(t.id)}
                          className={`py-2 px-3 rounded-xl border text-[11px] text-left transition-all flex items-center justify-between font-medium ${isSelected
                            ? 'bg-emerald-500/10 border-emerald-500 text-emerald-300 font-semibold'
                            : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:border-zinc-750'
                            }`}
                        >
                          <span>{t.label}</span>
                          {isSelected && <Check size={12} className="text-emerald-400 shrink-0" />}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Submit button */}
              <button
                type="submit"
                disabled={loading || (tab === 'register' && selectedTags.length !== 2)}
                className={`w-full mt-1.5 py-3 px-4 font-semibold rounded-xl flex items-center justify-center gap-2 transition-all text-xs ${loading
                  ? 'bg-zinc-850 text-zinc-600 cursor-not-allowed'
                  : tab === 'register' && selectedTags.length !== 2
                    ? 'bg-zinc-850 text-zinc-500 cursor-not-allowed border border-zinc-800'
                    : 'bg-emerald-500 hover:bg-emerald-400 text-zinc-950 shadow-lg hover:shadow-emerald-500/10 hover:scale-[1.01] active:scale-95'
                  }`}
              >
                {loading ? 'Đang xử lý...' : tab === 'login' ? 'Đăng nhập ngay' : 'Đăng ký & Bắt đầu Session'}
                <Play size={12} fill="currentColor" />
              </button>

            </form>
          </div>
        )}

        {/* Info Box */}
        <div className="w-full bg-zinc-950/60 rounded-2xl p-3 flex items-start gap-2.5 border border-zinc-800 shrink-0">
          <ShieldAlert size={18} className="text-emerald-400 shrink-0 mt-0.5" />
          <p className="text-[10px] text-zinc-500 leading-normal">
            Bằng cách tiếp tục, bạn đồng ý kích hoạt tính năng tự động theo dõi thời gian thực để ngăn ngừa hành vi doomscrolling. GoTouchGrass bảo mật quyền riêng tư của bạn.
          </p>
        </div>

        {/* Footer info */}
        <div className="text-[9px] text-zinc-700 mt-1 font-mono shrink-0">
          GoTouchGrass - Hackathon MVP v1.0
        </div>
      </div>
    </div>
  );
};
