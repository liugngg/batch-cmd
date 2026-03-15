# 命令行批量执行工具

## 1.主要功能：

1. 对于给定的命令行，可以提供图形界面批量执行，并将状态和结果输出到日志框中。

2. 需要批量执行的命令行可以保存到 json 文件中，还可以调用和编辑。

3. 支持批量执行完后自动关机的功能；

## 2. 打包命令

- 生成单文件格式（pyinstaller）
  `pyinstaller -i liug.ico -F -w cmd_batch.py --clean -n 命令行批量执行工具` 

- 生成单文件格式（Nuitka --onefile自动压缩）
  
  `python -m nuitka --mingw64 --onefile --lto=yes --show-progress --output-dir=dist --remove-output --plugin-enable=tk-inter --windows-console-mode=disable --windows-icon-from-ico=liug.ico cmd_batch.py`

  `uvx --from nuitka python -m nuitka --mingw64 --onefile --lto=yes --show-progress --output-dir=dist --remove-output --plugin-enable=tk-inter --windows-console-mode=disable --windows-icon-from-ico=liug.ico cmd_batch.py`

- 生成单文件格式（Nuitka --使用upx 压缩）
  
  `python -m nuitka --mingw64 --onefile --onefile-no-compression --plugin-enable=upx --lto=yes --show-progress --output-dir=dist --remove-output --plugin-enable=tk-inter --windows-console-mode=disable --windows-icon-from-ico=liug.ico cmd_batch.py`

## 3. 作者

- [liugngg (GitHub地址)](https://github.com/liugngg)
