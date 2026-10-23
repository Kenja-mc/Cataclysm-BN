if (BUILD_TESTING)
    file(GLOB CATACLYSM_BN_TEST_SOURCES
            ${CMAKE_SOURCE_DIR}/tests/*.cpp)

    # Enabling benchmarks
    add_definitions(-DCATCH_CONFIG_ENABLE_BENCHMARKING)

    # TODO: build MO files required for tests

    # Catch2 v2 uses __COUNTER__, which Clang 22 reports under -Wpedantic.
    set(CATCH2_COMPILE_OPTIONS $<$<CXX_COMPILER_ID:Clang>:-Wno-c2y-extensions>)

    if (TILES)
        add_executable(cata_test-tiles ${CATACLYSM_BN_TEST_SOURCES})
        target_link_libraries(cata_test-tiles PRIVATE cataclysm-bn-tiles-common)
        target_compile_options(cata_test-tiles PRIVATE ${CATCH2_COMPILE_OPTIONS})

        add_test(
            NAME test-tiles
            COMMAND sh -c "$<TARGET_FILE:cata_test-tiles> --rng-seed time"
            WORKING_DIRECTORY ${CMAKE_SOURCE_DIR})

        set_target_properties( cata_test-tiles PROPERTIES VS_DEBUGGER_WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}" )
        if (COMMAND cata_copy_windows_lavapipe_runtime)
            cata_copy_windows_lavapipe_runtime(cata_test-tiles)
        endif()
    endif ()

    if (CURSES)
        add_executable(cata_test ${CATACLYSM_BN_TEST_SOURCES})
        target_link_libraries(cata_test PRIVATE cataclysm-bn-common)
        target_compile_options(cata_test PRIVATE ${CATCH2_COMPILE_OPTIONS})

        add_test(
            NAME test
            COMMAND sh -c "$<TARGET_FILE:cata_test> --rng-seed time"
            WORKING_DIRECTORY ${CMAKE_SOURCE_DIR})

        if (COMMAND cata_copy_windows_lavapipe_runtime)
            cata_copy_windows_lavapipe_runtime(cata_test)
        endif()
    endif ()
endif ()
