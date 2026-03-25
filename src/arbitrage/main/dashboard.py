import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import sys
import os
from decimal import Decimal
from typing import List, Optional
from arbitrage.domain.entities.hedge_position import HedgePosition

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from arbitrage.infrastructure.persistence.hedge_position_repository_sqlite import HedgePositionRepositorySqlite
from arbitrage.infrastructure.persistence.sqlite_connection import SqliteConnection
from arbitrage.domain.entities.enums import PositionState, TradeSide

# 页面配置
st.set_page_config(
    page_title="套利交易监控面板",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
<style>
    .metric-card {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 16px;
        margin: 8px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .profit-positive {
        color: #00cc96;
        font-weight: bold;
    }
    .profit-negative {
        color: #ff6666;
        font-weight: bold;
    }
    .status-open {
        background-color: #e8f5e8;
        color: #2e7d32;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
    }
    .status-closing {
        background-color: #fff3e0;
        color: #ef6c00;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
    }
</style>
""", unsafe_allow_html=True)

class ArbitrageDashboard:
    def __init__(self):
        self.db_path = "data/arb.db"
        self.refresh_interval = 5  # 秒
        self.logs_dir = "logs"  # 日志目录
        
        # 初始化会话状态
        if 'search_results' not in st.session_state:
            st.session_state.search_results = None
        if 'last_search_keyword' not in st.session_state:
            st.session_state.last_search_keyword = ""
        if 'last_selected_files' not in st.session_state:
            st.session_state.last_selected_files = []
    
    def get_repository(self) -> HedgePositionRepositorySqlite:
        """获取仓位仓库实例"""
        conn = SqliteConnection(self.db_path)
        return HedgePositionRepositorySqlite(conn)
    
    def get_log_files(self) -> List[str]:
        """获取所有日志文件列表"""
        if not os.path.exists(self.logs_dir):
            return []
        
        log_files = []
        for file in os.listdir(self.logs_dir):
            if file.endswith('.log'):
                log_files.append(file)
        
        # 按修改时间排序，最新的在前面
        log_files.sort(key=lambda x: os.path.getmtime(os.path.join(self.logs_dir, x)), reverse=True)
        return log_files
    
    def search_logs(self, keyword: str = "", selected_files: List[str] = None) -> List[dict]:
        """搜索日志内容"""
        if not os.path.exists(self.logs_dir):
            return []
        
        results = []
        files_to_search = selected_files if selected_files else self.get_log_files()
        
        for filename in files_to_search:
            file_path = os.path.join(self.logs_dir, filename)
            if not os.path.exists(file_path):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                            
                        # 如果有搜索关键词，只返回匹配的行
                        if keyword and keyword.lower() not in line.lower():
                            continue
                        
                        # 解析日志行格式：[时间戳] [前缀] [级别] 消息内容
                        timestamp, prefix, level, message = "", "", "", ""
                        
                        # 提取时间戳 [2026-02-19 13:12:18]
                        if line.startswith('['):
                            end_time_idx = line.find(']')
                            if end_time_idx > 0:
                                timestamp = line[1:end_time_idx].strip()
                                remaining = line[end_time_idx + 1:].strip()
                                
                                # 提取前缀 [DRY-RUN]
                                if remaining.startswith('['):
                                    end_prefix_idx = remaining.find(']')
                                    if end_prefix_idx > 0:
                                        prefix = remaining[1:end_prefix_idx].strip()
                                        remaining = remaining[end_prefix_idx + 1:].strip()
                                        
                                        # 提取级别 [INFO]
                                        if remaining.startswith('['):
                                            end_level_idx = remaining.find(']')
                                            if end_level_idx > 0:
                                                level = remaining[1:end_level_idx].strip()
                                                message = remaining[end_level_idx + 1:].strip()
                                            else:
                                                message = remaining
                                        else:
                                            message = remaining
                                else:
                                    message = remaining
                            else:
                                message = line
                        else:
                            message = line
                        
                        results.append({
                            'file': filename,
                            'line_number': line_num,
                            'timestamp': timestamp,
                            'prefix': prefix,
                            'level': level,
                            'message': message,
                            'raw_line': line
                        })
            except Exception as e:
                st.warning(f"读取日志文件 {filename} 时出错: {str(e)}")
        
        # 按时间戳排序（最新的在前面）
        # 注意：这里的时间戳是字符串格式，需要特殊处理排序
        try:
            results.sort(key=lambda x: x['timestamp'], reverse=True)
        except:
            # 如果排序失败，至少保证有结果返回
            pass
            
        return results
    
    def calculate_account_summary(self, positions: List[HedgePosition]) -> dict:
        """计算账户总览数据"""
        total_notional = Decimal('0')
        total_pnl = Decimal('0')
        total_fees = Decimal('0')
        total_slippage = Decimal('0')
        open_positions_count = 0
        closed_positions_count = 0
        
        for position in positions:
            # 计算名义价值
            long_notional = position.long_leg.amount * position.long_leg.price
            short_notional = position.short_leg.amount * position.short_leg.price
            position_notional = (long_notional + short_notional) / 2
            
            total_notional += position_notional
            
            # 使用新的双边持仓收益计算公式
            # PNL = (入场短仓价格 - 入场多仓价格) - (当前短仓价格 - 当前多仓价格) - 成本
            entry_long_price = position.long_leg.price
            entry_short_price = position.short_leg.price
            
            # 对于未平仓的仓位，使用入场价格计算（假设平仓价格等于入场价格）
            # 对于已平仓的仓位，应该使用实际的平仓价格
            if hasattr(position.long_leg, 'close_price') and position.long_leg.close_price:
                exit_long_price = position.long_leg.close_price
            else:
                exit_long_price = entry_long_price  # 假设未平仓
            if hasattr(position.short_leg, 'close_price') and position.short_leg.close_price:
                exit_short_price = position.short_leg.close_price
            else:
                exit_short_price = entry_short_price  # 假设未平仓

            long_buy_price = entry_long_price if position.long_leg.side == TradeSide.BUY else exit_long_price
            long_sell_price = entry_long_price if position.long_leg.side == TradeSide.SELL else exit_long_price
            short_buy_price = entry_short_price if position.short_leg.side == TradeSide.BUY else exit_short_price
            short_sell_price = entry_short_price if position.short_leg.side == TradeSide.SELL else exit_short_price
            
            # 计算价格变动收益
            price_gain = (long_sell_price - long_buy_price) + (short_sell_price - short_buy_price)
            quantity = min(position.long_leg.amount, position.short_leg.amount)
            position_pnl = price_gain * quantity
            
            # 扣除成本
            total_cost = (position.long_leg.fee + position.short_leg.fee + 
                         position.long_leg.slippage_loss + position.short_leg.slippage_loss)
            position_pnl -= total_cost
            
            total_pnl += position_pnl
            total_fees += position.long_leg.fee + position.short_leg.fee
            total_slippage += position.long_leg.slippage_loss + position.short_leg.slippage_loss
            
            if position.state in [PositionState.OPEN, PositionState.CLOSING]:
                open_positions_count += 1
            else:
                closed_positions_count += 1
        
        # 计算利润率
        total_cost = total_notional + total_fees + total_slippage
        profit_rate = (total_pnl / total_cost * 100) if total_cost > 0 else Decimal('0')
        
        return {
            'total_notional': total_notional,
            'total_pnl': total_pnl,
            'total_fees': total_fees,
            'total_slippage': total_slippage,
            'profit_rate': profit_rate,
            'open_positions': open_positions_count,
            'closed_positions': closed_positions_count,
            'total_positions': len(positions)
        }
    
    def create_profit_chart(self, positions: List) -> go.Figure:
        """创建利润图表"""
        if not positions:
            # 返回空图表
            fig = go.Figure()
            fig.update_layout(
                title="暂无交易数据",
                xaxis_title="时间",
                yaxis_title="利润",
                height=400
            )
            return fig
        
        # 准备数据
        chart_data = []
        cumulative_pnl = Decimal('0')
        
        # 按时间排序
        sorted_positions = sorted(positions, key=lambda x: x.open_timestamp)
        
        for position in sorted_positions:
            # 使用新的收益计算公式
            entry_long_price = position.long_leg.price
            entry_short_price = position.short_leg.price
            
            # 使用入场价格作为退出价格（简化计算）
            if hasattr(position.long_leg, 'close_price') and position.long_leg.close_price:
                exit_long_price = position.long_leg.close_price
            else:
                exit_long_price = entry_long_price  # 假设未平仓
            if hasattr(position.short_leg, 'close_price') and position.short_leg.close_price:
                exit_short_price = position.short_leg.close_price
            else:
                exit_short_price = entry_short_price  # 假设未平仓
            

            long_buy_price = entry_long_price if position.long_leg.side == TradeSide.BUY else exit_long_price
            long_sell_price = entry_long_price if position.long_leg.side == TradeSide.SELL else exit_long_price
            short_buy_price = entry_short_price if position.short_leg.side == TradeSide.BUY else exit_short_price
            short_sell_price = entry_short_price if position.short_leg.side == TradeSide.SELL else exit_short_price
            
            # 计算价格变动收益
            # 计算该仓位的PNL
            price_gain = (long_sell_price - long_buy_price) + (short_sell_price - short_buy_price)
            quantity = min(position.long_leg.amount, position.short_leg.amount)
            position_pnl = price_gain * quantity
            
            # 扣除成本
            total_cost = (position.long_leg.fee + position.short_leg.fee + 
                         position.long_leg.slippage_loss + position.short_leg.slippage_loss)
            position_pnl -= total_cost
            
            cumulative_pnl += position_pnl
            
            # 计算该仓位的成本用于利润率计算
            long_value = position.long_leg.amount * position.long_leg.price
            short_value = position.short_leg.amount * position.short_leg.price
            position_cost = (abs(long_value) + abs(short_value)) + total_cost
            
            chart_data.append({
                'timestamp': datetime.fromtimestamp(position.open_timestamp),
                'cumulative_pnl': float(cumulative_pnl),
                'profit_rate': float((position_pnl / position_cost * 100)) if position_cost > 0 else 0,
                'position_pnl': float(position_pnl)
            })
        
        if not chart_data:
            fig = go.Figure()
            fig.update_layout(title="暂无有效数据", height=400)
            return fig
        
        # 创建双轴图表
        fig = go.Figure()
        
        # 累计利润线（右侧y轴）
        fig.add_trace(go.Scatter(
            x=[d['timestamp'] for d in chart_data],
            y=[d['cumulative_pnl'] for d in chart_data],
            mode='lines+markers',
            name='累计利润 (USD)',
            line=dict(color='#1f77b4', width=2),
            yaxis='y2'
        ))
        
        # 单笔利润散点图（右侧y轴）
        fig.add_trace(go.Scatter(
            x=[d['timestamp'] for d in chart_data],
            y=[d['position_pnl'] for d in chart_data],
            mode='markers',
            name='单笔利润 (USD)',
            marker=dict(color='#2ca02c', size=8),
            yaxis='y2'
        ))
        
        # 利润率线（左侧y轴）
        fig.add_trace(go.Scatter(
            x=[d['timestamp'] for d in chart_data],
            y=[d['profit_rate'] for d in chart_data],
            mode='lines+markers',
            name='单笔利润率 (%)',
            line=dict(color='#ff7f0e', width=2),
            yaxis='y1'
        ))
        
        # 更新布局
        fig.update_layout(
            title="利润趋势分析",
            xaxis_title="时间",
            yaxis=dict(
                title="利润率 (%)",
                side='left',
                showgrid=True
            ),
            yaxis2=dict(
                title="利润 (USD)",
                side='right',
                overlaying='y',
                showgrid=False
            ),
            height=400,
            showlegend=True,
            hovermode='x unified'
        )
        
        return fig
    
    def display_open_positions(self, positions: List) -> pd.DataFrame:
        """显示未关闭仓位列表"""
        open_positions = [p for p in positions if p.state in [PositionState.OPEN, PositionState.CLOSING]]
        
        if not open_positions:
            st.info("当前没有未关闭的仓位")
            return pd.DataFrame()
        
        # 转换为DataFrame
        data = []
        for position in open_positions:
            # 计算当前PNL
            long_value = position.long_leg.amount * position.long_leg.price
            short_value = position.short_leg.amount * position.short_leg.price
            current_pnl = (short_value - long_value) - (
                position.short_leg.fee + position.long_leg.fee + 
                position.short_leg.slippage_loss + position.long_leg.slippage_loss
            )
            
            data.append({
                '仓位ID': position.id[:8] + '...',
                '交易对': f"{position.pair.base}/{position.pair.quote}",
                '多头交易所': position.long_leg.exchange,
                '空头交易所': position.short_leg.exchange,
                '状态': position.state.value,
                '开仓时间': datetime.fromtimestamp(position.open_timestamp).strftime('%Y-%m-%d %H:%M:%S'),
                '多头数量': float(position.long_leg.amount),
                '空头数量': float(position.short_leg.amount),
                '多头价格': float(position.long_leg.price),
                '空头价格': float(position.short_leg.price),
                '当前PNL': float(current_pnl),
                '手续费': float(position.long_leg.fee + position.short_leg.fee),
                '滑点损失': float(position.long_leg.slippage_loss + position.short_leg.slippage_loss)
            })
        
        df = pd.DataFrame(data)
        return df
    
    def run_dashboard(self):
        """运行仪表板"""
        st.title("📊 套利交易监控面板")
        
        # 侧边栏配置
        with st.sidebar:
            st.header("⚙️ 配置")
            self.refresh_interval = st.slider("刷新间隔(秒)", 1, 60, 5)
            
            # 日志搜索配置
            st.markdown("---")
            st.header("📝 日志搜索")
            search_keyword = st.text_input("搜索关键词", key="log_search_keyword")
            
            # 获取日志文件列表
            log_files = self.get_log_files()
            if log_files:
                selected_files = st.multiselect(
                    "选择日志文件",
                    options=log_files,
                    default=log_files[:3] if len(log_files) <= 3 else log_files[:1],
                    key="selected_log_files"
                )
            else:
                selected_files = []
                st.info("未找到日志文件")
            
            search_button = st.button("搜索日志", key="search_logs_btn")
            
            # 处理搜索逻辑
            if search_button:
                st.session_state.search_results = self.search_logs(search_keyword, selected_files)
                st.session_state.last_search_keyword = search_keyword
                st.session_state.last_selected_files = selected_files
            
            st.markdown("---")
            st.markdown("**数据库状态**")
            if os.path.exists(self.db_path):
                db_size = os.path.getsize(self.db_path) / (1024 * 1024)  # MB
                st.success(f"✓ 数据库连接正常 ({db_size:.2f} MB)")
            else:
                st.error("✗ 数据库文件不存在")
        
        # 自动刷新占位符
        refresh_placeholder = st.empty()
        
        repository = self.get_repository()
        all_positions = repository.get_all_positions()
        # 主要内容区域
        try:
            
            if not all_positions:
                st.warning("⚠️ 暂无交易数据，请先运行套利策略")
                return
            
            # 计算账户总览
            summary = self.calculate_account_summary(all_positions)
            
            # 第一部分：账户总额概览
            st.header("💰 账户总览")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    label="总名义价值",
                    value=f"${float(summary['total_notional']):,.2f}",
                    delta=None
                )
            
            with col2:
                pnl_color = "normal" if summary['total_pnl'] >= 0 else "inverse"
                st.metric(
                    label="总盈亏",
                    value=f"${float(summary['total_pnl']):,.2f}",
                    delta=None,
                    delta_color=pnl_color
                )
            
            with col3:
                rate_color = "normal" if summary['profit_rate'] >= 0 else "inverse"
                st.metric(
                    label="总利润率",
                    value=f"{float(summary['profit_rate']):.2f}%",
                    delta=None,
                    delta_color=rate_color
                )
            
            with col4:
                st.metric(
                    label="活跃仓位数",
                    value=f"{summary['open_positions']}/{summary['total_positions']}",
                    delta=None
                )
            
            # 第二部分：费用明细
            st.subheader("📋 费用明细")
            fee_col1, fee_col2, fee_col3 = st.columns(3)
            
            with fee_col1:
                st.metric("总手续费", f"${float(summary['total_fees']):,.2f}")
            
            with fee_col2:
                st.metric("总滑点损失", f"${float(summary['total_slippage']):,.2f}")
            
            with fee_col3:
                total_cost = summary['total_fees'] + summary['total_slippage']
                st.metric("总成本", f"${float(total_cost):,.2f}")
            
            # 第二部分：利润图表
            st.header("📈 利润趋势")
            profit_fig = self.create_profit_chart(all_positions)
            st.plotly_chart(profit_fig, use_container_width=True)
            
            # 第三部分：未关闭仓位列表
            st.header("📋 当前未关闭仓位")
            open_positions_df = self.display_open_positions(all_positions)
            
            if not open_positions_df.empty:
                # 使用DataFrame的styler功能来应用样式
                def highlight_status(status):
                    styles = []
                    if status == 'open':
                        styles.append('background-color: #e8f5e8; color: #2e7d32; padding: 4px 8px; border-radius: 4px; font-weight: bold;')
                    elif status == 'closing':
                        styles.append('background-color: #fff3e0; color: #ef6c00; padding: 4px 8px; border-radius: 4px; font-weight: bold;')
                    return '; '.join(styles)
                
                # 创建样式化的DataFrame
                styled_df = open_positions_df.style.applymap(
                    lambda x: highlight_status(x) if x in ['open', 'closing'] else '',
                    subset=['状态']
                )
                
                # 显示表格
                st.dataframe(
                    styled_df,
                    use_container_width=True,
                    height=400
                )
                
                # 添加仓位详情展开
                st.subheader("🔍 仓位详情")
                selected_position = st.selectbox(
                    "选择仓位查看详情",
                    options=open_positions_df['仓位ID'].tolist(),
                    key="position_detail"
                )
                
                if selected_position:
                    position_detail = open_positions_df[open_positions_df['仓位ID'] == selected_position].iloc[0]
                    st.json(position_detail.to_dict())
            
            # 第四部分：实时日志搜索和显示
            st.header("📝 实时日志")
            
            # 日志统计信息
            log_files = self.get_log_files()
            if log_files:
                total_files = len(log_files)
                total_size = sum(os.path.getsize(os.path.join(self.logs_dir, f)) for f in log_files)
                
                log_stats_col1, log_stats_col2 = st.columns(2)
                with log_stats_col1:
                    st.metric("日志文件数量", total_files)
                with log_stats_col2:
                    st.metric("总大小", f"{total_size / (1024*1024):.2f} MB")
                
                # 搜索结果显示
                # 检查是否有保存的搜索结果
                has_saved_results = (st.session_state.search_results is not None and 
                                   len(st.session_state.search_results) > 0)
                
                if has_saved_results:
                    search_results = st.session_state.search_results
                    st.success(f"找到 {len(search_results)} 条匹配记录")
                    
                    # 按文件分组结果
                    grouped_results = {}
                    for result in search_results:
                        file_key = result['file']
                        if file_key not in grouped_results:
                            grouped_results[file_key] = []
                        grouped_results[file_key].append(result)
                    
                    # 显示分组后的结果
                    for file_name, file_results in grouped_results.items():
                        with st.expander(f"📄 {file_name} ({len(file_results)} 条匹配)", expanded=False):
                            # 显示该文件的所有匹配结果
                            for i, result in enumerate(file_results[:50]):  # 限制每个文件显示前50条
                                # 显示日志详情
                                cols = st.columns([2, 1, 1, 3])
                                with cols[0]:
                                    st.caption(f"**时间**: {result['timestamp']}")
                                with cols[1]:
                                    st.caption(f"**前缀**: {result['prefix']}")
                                with cols[2]:
                                    # 根据日志级别设置颜色
                                    level_color = {
                                        'ERROR': '🔴',
                                        'WARNING': '🟠', 
                                        'INFO': '🔵',
                                        'DEBUG': '⚪'
                                    }.get(result['level'], '⚫')
                                    st.caption(f"**级别**: {level_color} {result['level']}")
                                with cols[3]:
                                    st.caption(f"**行号**: {result['line_number']}")
                                
                                # 高亮显示搜索关键词
                                message = result['message']
                                if st.session_state.last_search_keyword:
                                    # 简单的关键词高亮
                                    highlighted_message = message.replace(
                                        st.session_state.last_search_keyword, 
                                        f"**{st.session_state.last_search_keyword}**"
                                    )
                                    st.markdown(highlighted_message)
                                else:
                                    st.text(message)
                                
                                if i < len(file_results) - 1:  # 不是最后一条才加分隔线
                                    st.divider()
                            
                            if len(file_results) > 50:
                                st.info(f"此文件显示前50条结果，共 {len(file_results)} 条匹配记录")
                    
                    # 显示总计信息
                    total_displayed = sum(min(len(results), 50) for results in grouped_results.values())
                    if total_displayed < len(search_results):
                        st.info(f"显示 {total_displayed} 条结果，共找到 {len(search_results)} 条匹配记录")
                else:
                    st.info("未找到匹配的日志记录")
            else:
                st.info("日志目录不存在或无日志文件")
            
            # 显示最后更新时间
            refresh_placeholder.markdown(
                f"<small style='color: gray;'>最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small>",
                unsafe_allow_html=True
            )
            
        except Exception as e:
            st.error(f"❌ 数据加载失败: {str(e)}")
            st.exception(e)

def main():
    dashboard = ArbitrageDashboard()
    
    # 运行仪表板
    dashboard.run_dashboard()
    
    # 自动刷新
    time.sleep(dashboard.refresh_interval)
    st.rerun()

if __name__ == "__main__":
    main()