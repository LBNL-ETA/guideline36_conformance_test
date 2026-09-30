

def cli():
    import argparse
    # Parse command-line arguments first
    parser = argparse.ArgumentParser(
        description="Run ASHRAE Guideline 36 conformance tests"
    )
    parser.add_argument(
        "--global-config",
        help="path to global config file (default: config/global_config.yaml)",
        default=None
    )
    parser.add_argument(
        "--test-config",
        help="path to test-specific config file (default: determined from test_type)",
        default=None
    )
    parser.add_argument("--reset", help="reset point values to first stage (overrides config)", action='store_true')
    parser.add_argument("--output", help="print point values without running test (overrides config)", action='store_true')
    parser.add_argument("--csv", help="save outputs to csv (overrides config)", action='store_true')
    parser.add_argument("--name", help="test run name (overrides config)", default=None)

    import sys
    args = parser.parse_args(sys.argv[1:]) # thought i didn't have to write this arg in
    
    # Initialize test with config files
    from .Test import Test
    test = Test(
        global_config_path=args.global_config,
        test_config_path=args.test_config
    )
    
    # Get test_runner config with defaults
    test_runner_config = test.config.get('test_runner', {})
    
    # Extract CLI arguments with fallback to config values
    # All boolean flags use: CLI flag OR config value OR False
    reset = args.reset or test_runner_config.get('reset_points', False)
    output = args.output or test_runner_config.get('print_output', False)
    to_csv = args.csv or test_runner_config.get('save_csv', False)
    
    # Name uses: CLI value OR config value OR timestamp
    import time
    name = args.name or test_runner_config.get('name') or time.strftime("%Y%m%dT%H%M%S")

    print(to_csv)
    print(name)

    if reset:
        print("resetting points")
        test.set_values(variable_value_dict=test.ip.iloc[1].to_dict())
        points = test.read_points()
        cool_loop_output = points['CoolLoopOut']

        while cool_loop_output != 0:
            print("waiting for cooling loop output to drop to 0, current value = %f"%cool_loop_output)
            time.sleep(3)
            points = test.read_points()
            cool_loop_output = points['CoolLoopOut']

        print()
        test.print_points()
    elif output:
        print("printing values")
        test.print_points()
    else:
        # print("starting test; Current values=")
        # test.print_points()
        test.start_test(to_csv=to_csv, name=name)

        # Opt-in post-test hook: launch the interactive viz UI when both
        # save_csv and viz.enabled are true. Guarded behind the config so
        # existing behavior is untouched for anyone who doesn't set it.
        viz_cfg = test.config.get('viz', {}) or {}
        if to_csv and viz_cfg.get('enabled', False):
            try:
                from viz.launcher import launch_after_test
            except ImportError as e:
                print(
                    "[viz] viz.enabled is true but the viz extras are not "
                    "installed (streamlit/plotly missing). Install with "
                    "`pip install .[viz]` or run in the pixi `simulation`/"
                    f"`bacnet`/`viz` environment. Skipping. ({e})"
                )
            else:
                run_dir = test.results_dir / f"run_{name}"
                launch_after_test(
                    run_dir,
                    port=int(viz_cfg.get('port', 8501)),
                    address=str(viz_cfg.get('address', '0.0.0.0')),
                )

if __name__ == "__main__":
    cli()
